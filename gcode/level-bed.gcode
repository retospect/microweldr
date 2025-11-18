; Bed leveling sequence
; Homes first, then runs auto bed leveling

G28        ; Home all axes first
G29        ; Auto bed leveling (probe bed surface)
M500       ; Save bed leveling data to EEPROM
M117 Bed leveling complete  ; Display message
