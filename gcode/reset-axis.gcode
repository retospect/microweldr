; Reset all axes to home position
; Safe axis reset sequence

G28        ; Home all axes (X, Y, Z)
G90        ; Set absolute positioning mode
G92 E0     ; Reset extruder position to zero
M84        ; Disable stepper motors after homing
