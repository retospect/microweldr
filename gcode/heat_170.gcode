; Heat nozzle to 170°C and bed to 35°C
; Wait for both temperatures to be reached

M140 S35       ; Set bed temperature to 35°C
M104 S170      ; Set nozzle temperature to 170°C
M109 S170      ; Wait for nozzle to reach 170°C
M190 S35       ; Wait for bed to reach 35°C
M117 Heated to 170C  ; Display message
