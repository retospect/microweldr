"""Enhanced CLI interface with click and improved UX."""

import logging
import sys
import time
from pathlib import Path
from typing import Optional

import click
from tqdm import tqdm

from ..core.config import Config
from ..core.svg_parser import SVGParser
from ..core.gcode_generator import GCodeGenerator
from ..core.safety import validate_weld_operation, SafetyError
from ..core.security import validate_secrets_interactive, create_secure_secrets_template
from ..core.graceful_degradation import ResilientPrusaLinkClient, check_system_health
from ..core.resource_management import safe_gcode_generation, TemporaryFileManager
from ..core.progress import progress_context
from ..core.caching import OptimizedSVGParser
from ..core.logging_config import setup_logging, LogContext
from ..animation.generator import AnimationGenerator
from ..validation.validators import SVGValidator, GCodeValidator


# Custom click decorators for common options
def common_options(func):
    """Common CLI options decorator."""
    func = click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')(func)
    func = click.option('--quiet', '-q', is_flag=True, help='Suppress non-error output')(func)
    func = click.option('--config', '-c', default='config.toml', 
                       help='Configuration file path', type=click.Path(exists=True))(func)
    func = click.option('--log-file', help='Log file path')(func)
    return func


def printer_options(func):
    """Printer-related CLI options decorator."""
    func = click.option('--secrets', default='secrets.toml',
                       help='Secrets configuration file', type=click.Path())(func)
    func = click.option('--submit-to-printer', is_flag=True,
                       help='Submit G-code to printer after generation')(func)
    func = click.option('--auto-start', is_flag=True,
                       help='Automatically start print after upload')(func)
    func = click.option('--storage', type=click.Choice(['local', 'usb']), default='local',
                       help='Printer storage location')(func)
    return func


@click.group()
@click.version_option(version='3.0.2', prog_name='MicroWeldr')
@click.pass_context
def cli(ctx):
    """MicroWeldr - Convert SVG files to G-code for plastic welding.
    
    A comprehensive tool for converting SVG designs into G-code for
    plastic welding on Prusa Core One printers.
    """
    ctx.ensure_object(dict)


@cli.command()
@click.argument('svg_file', type=click.Path(exists=True, path_type=Path))
@click.option('--output', '-o', help='Output G-code file path')
@click.option('--animation', '-a', help='Output animation SVG file path')
@click.option('--skip-bed-leveling', is_flag=True, help='Skip bed leveling in G-code')
@click.option('--dry-run', is_flag=True, help='Generate files but don\'t send to printer')
@click.option('--validate-only', is_flag=True, help='Only validate input, don\'t generate')
@click.option('--force', is_flag=True, help='Force generation despite warnings')
@click.option('--cache/--no-cache', default=True, help='Enable/disable SVG parsing cache')
@common_options
@printer_options
@click.pass_context
def weld(ctx, svg_file, output, animation, skip_bed_leveling, dry_run, validate_only, 
         force, cache, verbose, quiet, config, log_file, secrets, submit_to_printer, 
         auto_start, storage):
    """Generate G-code for welding from SVG file.
    
    This command processes an SVG file and generates G-code for plastic welding.
    It can also create an animated visualization and optionally submit the job
    to a connected Prusa printer.
    
    Examples:
    
        # Basic usage
        microweldr weld design.svg
        
        # Generate with custom output and animation
        microweldr weld design.svg -o weld.gcode -a animation.svg
        
        # Submit directly to printer
        microweldr weld design.svg --submit-to-printer --auto-start
        
        # Validate only (no generation)
        microweldr weld design.svg --validate-only
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    setup_logging(level=log_level, log_file=log_file, console=not quiet)
    
    logger = logging.getLogger(__name__)
    
    with LogContext("weld_generation"):
        try:
            # Load configuration
            with click.progressbar(length=1, label='Loading configuration') as bar:
                config_obj = Config(config)
                bar.update(1)
            
            # Validate secrets if printer submission is requested
            if submit_to_printer:
                if not Path(secrets).exists():
                    click.echo(f"❌ Secrets file not found: {secrets}")
                    if click.confirm("Create a secure secrets template?"):
                        create_secure_secrets_template(secrets)
                        click.echo(f"✅ Created {secrets}. Please edit it with your printer details.")
                        return
                    else:
                        raise click.Abort()
                
                if not validate_secrets_interactive(secrets):
                    if not force:
                        click.echo("❌ Security validation failed. Use --force to override.")
                        raise click.Abort()
                    else:
                        click.echo("⚠️  Proceeding despite security warnings (--force used)")
            
            # Parse SVG with progress and caching
            click.echo(f"📄 Processing SVG: {svg_file}")
            
            if cache:
                parser = OptimizedSVGParser(cache_enabled=True)
                weld_paths = parser.parse_svg_file(svg_file)
                
                # Show cache statistics
                stats = parser.get_stats()
                if stats['cache_hits'] > 0:
                    click.echo(f"💾 Cache hit rate: {stats['cache_hit_rate']:.1f}%")
            else:
                parser = SVGParser()
                weld_paths = parser.parse_file(svg_file)
            
            if not weld_paths:
                click.echo("❌ No weld paths found in SVG file")
                raise click.Abort()
            
            total_points = sum(len(path.points) for path in weld_paths)
            click.echo(f"✅ Parsed {len(weld_paths)} paths with {total_points} points")
            
            # Safety validation
            click.echo("🔒 Validating safety parameters...")
            warnings, errors = validate_weld_operation(weld_paths, config_obj.config)
            
            if errors:
                click.echo("❌ Safety validation failed:")
                for error in errors:
                    click.echo(f"   • {error}")
                if not force:
                    raise click.Abort()
                else:
                    click.echo("⚠️  Proceeding despite safety errors (--force used)")
            
            if warnings:
                click.echo("⚠️  Safety warnings:")
                for warning in warnings:
                    click.echo(f"   • {warning}")
                if not force and not click.confirm("Continue despite warnings?"):
                    raise click.Abort()
            
            if validate_only:
                click.echo("✅ Validation completed successfully")
                return
            
            # Generate output file paths
            if not output:
                output = svg_file.with_suffix('.gcode')
            else:
                output = Path(output)
            
            if animation and not Path(animation).suffix:
                animation = Path(animation).with_suffix('.svg')
            elif not animation:
                animation = svg_file.with_suffix('_animation.svg')
            else:
                animation = Path(animation)
            
            # Generate G-code with progress
            click.echo(f"⚙️  Generating G-code: {output}")
            
            with safe_gcode_generation(output, backup=True) as temp_gcode_path:
                generator = GCodeGenerator(config_obj)
                
                with progress_context(len(weld_paths), "Generating G-code") as progress:
                    generator.generate(weld_paths, str(temp_gcode_path), skip_bed_leveling=skip_bed_leveling)
                    progress.update(len(weld_paths))
            
            # Validate generated G-code
            validator = GCodeValidator()
            result = validator.validate(str(output))
            
            if not result.is_valid:
                click.echo("⚠️  G-code validation warnings:")
                for warning in result.warnings:
                    click.echo(f"   • {warning}")
            
            # Generate animation
            if animation:
                click.echo(f"🎬 Generating animation: {animation}")
                
                anim_generator = AnimationGenerator(config_obj)
                anim_generator.generate(weld_paths, str(animation))
                
                click.echo(f"✅ Animation saved: {animation}")
            
            # Display file information
            gcode_size = output.stat().st_size
            click.echo(f"✅ G-code generated: {output} ({gcode_size:,} bytes)")
            
            # Estimate print time
            estimated_time = _estimate_print_time(weld_paths, config_obj.config)
            click.echo(f"⏱️  Estimated print time: {estimated_time}")
            
            # Submit to printer if requested
            if submit_to_printer and not dry_run:
                _submit_to_printer(output, secrets, auto_start, storage)
            elif dry_run:
                click.echo("🔍 Dry run completed - files generated but not sent to printer")
            
            click.echo("🎉 Welding preparation completed successfully!")
            
        except SafetyError as e:
            logger.error(f"Safety validation failed: {e}")
            click.echo(f"❌ Safety error: {e}")
            raise click.Abort()
        except Exception as e:
            logger.error(f"Weld generation failed: {e}", exc_info=True)
            click.echo(f"❌ Error: {e}")
            raise click.Abort()


@cli.command()
@click.argument('svg_file', type=click.Path(exists=True, path_type=Path))
@common_options
@click.pass_context
def validate(ctx, svg_file, verbose, quiet, config, log_file):
    """Validate SVG file for welding compatibility.
    
    Performs comprehensive validation of the SVG file including:
    - SVG structure and syntax
    - Weld parameter safety
    - Configuration compatibility
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    setup_logging(level=log_level, log_file=log_file, console=not quiet)
    
    click.echo(f"🔍 Validating SVG file: {svg_file}")
    
    try:
        # Validate SVG structure
        svg_validator = SVGValidator()
        svg_result = svg_validator.validate(str(svg_file))
        
        if svg_result.is_valid:
            click.echo("✅ SVG structure validation passed")
        else:
            click.echo("❌ SVG structure validation failed")
            click.echo(f"   Error: {svg_result.message}")
            return
        
        # Load configuration and parse
        config_obj = Config(config)
        parser = SVGParser()
        weld_paths = parser.parse_file(svg_file)
        
        if not weld_paths:
            click.echo("❌ No weld paths found in SVG")
            return
        
        # Safety validation
        warnings, errors = validate_weld_operation(weld_paths, config_obj.config)
        
        if errors:
            click.echo("❌ Safety validation failed:")
            for error in errors:
                click.echo(f"   • {error}")
        else:
            click.echo("✅ Safety validation passed")
        
        if warnings:
            click.echo("⚠️  Validation warnings:")
            for warning in warnings:
                click.echo(f"   • {warning}")
        
        # Summary
        total_points = sum(len(path.points) for path in weld_paths)
        click.echo(f"\n📊 Summary:")
        click.echo(f"   • Paths: {len(weld_paths)}")
        click.echo(f"   • Points: {total_points}")
        click.echo(f"   • Errors: {len(errors)}")
        click.echo(f"   • Warnings: {len(warnings)}")
        
        if errors:
            raise click.Abort()
        
    except Exception as e:
        click.echo(f"❌ Validation failed: {e}")
        raise click.Abort()


@cli.command()
@click.option('--secrets', default='secrets.toml', help='Secrets file path')
@common_options
@click.pass_context
def status(ctx, secrets, verbose, quiet, config, log_file):
    """Check printer and system status.
    
    Displays comprehensive status information including:
    - Printer connectivity and state
    - System health checks
    - Configuration validation
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    setup_logging(level=log_level, log_file=log_file, console=not quiet)
    
    click.echo("🔍 Checking system status...")
    
    # System health check
    health = check_system_health()
    
    click.echo(f"\n🏥 System Health: {health['overall'].upper()}")
    
    for component, status in health['components'].items():
        emoji = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"
        click.echo(f"   {emoji} {component.title()}: {status}")
    
    if health['warnings']:
        click.echo("\n⚠️  Warnings:")
        for warning in health['warnings']:
            click.echo(f"   • {warning}")
    
    if health['errors']:
        click.echo("\n❌ Errors:")
        for error in health['errors']:
            click.echo(f"   • {error}")
    
    # Printer status
    if Path(secrets).exists():
        try:
            client = ResilientPrusaLinkClient(secrets)
            printer_status = client.get_status()
            
            if printer_status.get('fallback'):
                click.echo("\n🖨️  Printer: ❌ Connection failed (fallback mode)")
            else:
                state = printer_status.get('printer', {}).get('state', 'Unknown')
                emoji = "🟢" if state == "Operational" else "🔥" if state == "Printing" else "⏸️" if state == "Paused" else "❌"
                click.echo(f"\n🖨️  Printer: {emoji} {state}")
                
                # Temperature info
                bed_temp = printer_status.get('printer', {}).get('temp_bed', {})
                nozzle_temp = printer_status.get('printer', {}).get('temp_nozzle', {})
                
                if bed_temp:
                    click.echo(f"   🌡️  Bed: {bed_temp.get('actual', 0):.1f}°C (target: {bed_temp.get('target', 0):.1f}°C)")
                if nozzle_temp:
                    click.echo(f"   🌡️  Nozzle: {nozzle_temp.get('actual', 0):.1f}°C (target: {nozzle_temp.get('target', 0):.1f}°C)")
        
        except Exception as e:
            click.echo(f"\n🖨️  Printer: ❌ Connection failed ({e})")
    else:
        click.echo(f"\n🖨️  Printer: ⚠️  No secrets file found ({secrets})")


@cli.command()
@click.option('--output', '-o', default='secrets.toml', help='Output secrets file path')
@click.option('--force', is_flag=True, help='Overwrite existing file')
@common_options
@click.pass_context
def init_secrets(ctx, output, force, verbose, quiet, config, log_file):
    """Initialize secure secrets configuration file.
    
    Creates a secure template for printer authentication with:
    - Strong password generation
    - Secure file permissions
    - Comprehensive security guidance
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    setup_logging(level=log_level, log_file=log_file, console=not quiet)
    
    output_path = Path(output)
    
    if output_path.exists() and not force:
        if not click.confirm(f"File {output} already exists. Overwrite?"):
            click.echo("❌ Aborted")
            return
    
    try:
        create_secure_secrets_template(str(output_path))
        click.echo(f"✅ Secure secrets template created: {output}")
        click.echo("🔒 Please review and customize the generated credentials")
        click.echo("⚠️  Remember to keep this file secure and never commit it to version control")
        
    except Exception as e:
        click.echo(f"❌ Failed to create secrets file: {e}")
        raise click.Abort()


def _estimate_print_time(weld_paths, config):
    """Estimate total print time."""
    total_points = sum(len(path.points) for path in weld_paths)
    
    # Rough estimation based on weld times and movement
    avg_weld_time = config.get('normal_welds', {}).get('weld_time', 0.1)
    avg_move_time = 0.05  # Rough estimate for movement between points
    
    total_time = total_points * (avg_weld_time + avg_move_time)
    
    if total_time < 60:
        return f"{total_time:.0f}s"
    elif total_time < 3600:
        return f"{total_time/60:.1f}m"
    else:
        return f"{total_time/3600:.1f}h"


def _submit_to_printer(gcode_path, secrets_path, auto_start, storage):
    """Submit G-code to printer."""
    click.echo("🚀 Submitting to printer...")
    
    try:
        client = ResilientPrusaLinkClient(secrets_path)
        
        # Check printer status first
        status = client.get_status()
        if status.get('fallback'):
            click.echo("⚠️  Printer connection degraded - manual upload required")
            return
        
        printer_state = status.get('printer', {}).get('state', 'Unknown')
        if printer_state not in ['Operational', 'Finished']:
            click.echo(f"⚠️  Printer not ready (state: {printer_state})")
            if not click.confirm("Continue anyway?"):
                return
        
        # Upload file
        filename = gcode_path.name
        
        with click.progressbar(length=1, label='Uploading to printer') as bar:
            result = client.upload_file(str(gcode_path), filename, auto_start=auto_start)
            bar.update(1)
        
        if result.get('fallback'):
            click.echo("⚠️  Upload failed - manual upload instructions provided")
        else:
            click.echo(f"✅ File uploaded: {result.get('filename', filename)}")
            
            if auto_start:
                if result.get('auto_started'):
                    click.echo("🔥 Print started automatically")
                else:
                    # Try to start manually
                    if client.start_print(filename):
                        click.echo("🔥 Print started")
                    else:
                        click.echo("⚠️  Could not start print automatically")
            else:
                click.echo("📁 File ready for manual printing")
    
    except Exception as e:
        click.echo(f"❌ Printer submission failed: {e}")


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
