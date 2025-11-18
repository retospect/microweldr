; Heat nozzle to 160°C and bed to 35°C
; Wait for both temperatures to be reached

M140 S45       ; Set bed temperature to 35°C
M104 S160      ; Set nozzle temperature to 160°C
M109 S160      ; Wait for nozzle to reach 160°C
M190 S45       ; Wait for bed to reach 35°C
M117 Heated to 160C  ; Display message
