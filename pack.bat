@ECHO OFF

SET PROJECT=alpha-protocol-test

CALL activate.bat
RD /S /Q bin 2>NUL
ECHO Freezing...
CALL cxfreeze %PROJECT%.py -s --base-name=Win32GUI --target-dir bin/raw >NUL
ECHO Packaging...
CALL misc\7za a -sfx7z.sfx bin/%PROJECT% ./bin/raw/* >NUL
ECHO Done.
