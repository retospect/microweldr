; Weld 10 dots test sequence
; First set: 160°C at Z0.1 (10 dots) - Normal weld
; Second set: 160°C at Z0.35 (10 dots) - Light weld
; Both sets: 1mm spacing between dots

; Setup - bed temp always 45°C
M140 S45       ; Set bed temperature to 45°C

; Home and position
G28            ; Home all axes
G90            ; Absolute positioning
G1 Z5 F3000     ; Move to 5mm height for safe XY movement
G1 X125 Y50 F3000  ; Move to middle front of bed (assuming 250mm bed)

; === FIRST SET: 160°C at Z0.1 ===
M104 S160      ; Set nozzle to 160°C
M109 S160      ; Wait for 160°C
M190 S45       ; Wait for bed to reach 45°C
M117 Welding 160C Z0.1  ; Display message

; Weld 10 dots at 160°C, Z0.1
G1 X120 F3000  ; Move to start position
G1 Z0.1 F3000   ; Down to weld position
G4 P500        ; Dwell 0.5s (weld dot 1)
G1 Z0.6 F3000   ; Up to travel height
G1 X121 F3000  ; Move 1mm
G1 Z0.1 F3000   ; Down to weld position
G4 P500        ; Dwell 0.5s (weld dot 2)
G1 Z0.6 F3000   ; Up to travel height
G1 X122 F3000  ; Move 1mm
G1 Z0.1 F3000   ; Down to weld position
G4 P500        ; Dwell 0.5s (weld dot 3)
G1 Z0.6 F3000   ; Up to travel height
G1 X123 F3000  ; Move 1mm
G1 Z0.1 F3000   ; Down to weld position
G4 P500        ; Dwell 0.5s (weld dot 4)
G1 Z0.6 F3000   ; Up to travel height
G1 X124 F3000  ; Move 1mm
G1 Z0.1 F3000   ; Down to weld position
G4 P500        ; Dwell 0.5s (weld dot 5)
G1 Z0.6 F3000   ; Up to travel height
G1 X125 F3000  ; Move 1mm
G1 Z0.1 F3000   ; Down to weld position
G4 P500        ; Dwell 0.5s (weld dot 6)
G1 Z0.6 F3000   ; Up to travel height
G1 X126 F3000  ; Move 1mm
G1 Z0.1 F3000   ; Down to weld position
G4 P500        ; Dwell 0.5s (weld dot 7)
G1 Z0.6 F3000   ; Up to travel height
G1 X127 F3000  ; Move 1mm
G1 Z0.1 F3000   ; Down to weld position
G4 P500        ; Dwell 0.5s (weld dot 8)
G1 Z0.6 F3000   ; Up to travel height
G1 X128 F3000  ; Move 1mm
G1 Z0.1 F3000   ; Down to weld position
G4 P500        ; Dwell 0.5s (weld dot 9)
G1 Z0.6 F3000   ; Up to travel height
G1 X129 F3000  ; Move 1mm
G1 Z0.1 F3000   ; Down to weld position
G4 P500        ; Dwell 0.5s (weld dot 10)
G1 Z0.6 F3000   ; Up to travel height

; Lift and move to second row
G1 Z5 F3000     ; Lift to 5mm height for safe travel
G1 Y60 F3000   ; Move to second row (10mm forward)

; === SECOND SET: 160°C at Z0.35 (Light Weld) ===
M117 Welding 160C Z0.35 Light  ; Display message

; Weld 10 dots at 160°C, Z0.35 (light weld) - 1mm spacing
G1 X120 F3000  ; Move to start position
G1 Z0.35 F3000  ; Down to light weld position
G4 P500        ; Dwell 0.5s (weld dot 1)
G1 Z0.6 F3000   ; Up to travel height
G1 X121 F3000  ; Move 1mm
G1 Z0.35 F3000  ; Down to light weld position
G4 P500        ; Dwell 0.5s (weld dot 2)
G1 Z0.6 F3000   ; Up to travel height
G1 X122 F3000  ; Move 1mm
G1 Z0.35 F3000  ; Down to light weld position
G4 P500        ; Dwell 0.5s (weld dot 3)
G1 Z0.6 F3000   ; Up to travel height
G1 X123 F3000  ; Move 1mm
G1 Z0.35 F3000  ; Down to light weld position
G4 P500        ; Dwell 0.5s (weld dot 4)
G1 Z0.6 F3000   ; Up to travel height
G1 X124 F3000  ; Move 1mm
G1 Z0.35 F3000  ; Down to light weld position
G4 P500        ; Dwell 0.5s (weld dot 5)
G1 Z0.6 F3000   ; Up to travel height
G1 X125 F3000  ; Move 1mm
G1 Z0.35 F3000  ; Down to light weld position
G4 P500        ; Dwell 0.5s (weld dot 6)
G1 Z0.6 F3000   ; Up to travel height
G1 X126 F3000  ; Move 1mm
G1 Z0.35 F3000  ; Down to light weld position
G4 P500        ; Dwell 0.5s (weld dot 7)
G1 Z0.6 F3000   ; Up to travel height
G1 X127 F3000  ; Move 1mm
G1 Z0.35 F3000  ; Down to light weld position
G4 P500        ; Dwell 0.5s (weld dot 8)
G1 Z0.6 F3000   ; Up to travel height
G1 X128 F3000  ; Move 1mm
G1 Z0.35 F3000  ; Down to light weld position
G4 P500        ; Dwell 0.5s (weld dot 9)
G1 Z0.6 F3000   ; Up to travel height
G1 X129 F3000  ; Move 1mm
G1 Z0.35 F3000  ; Down to light weld position
G4 P500        ; Dwell 0.5s (weld dot 10)
G1 Z0.6 F3000   ; Up to travel height

; === CLEANUP ===
G1 Z50 F3000    ; Lift to 50mm height
M104 S160      ; Set nozzle temperature to 160°C
M140 S45       ; Keep bed at 45°C
M117 Weld test complete  ; Display message
