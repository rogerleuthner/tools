

@echo off
rem USAGE: GDAL.bat <file to process - no spaces in name> <zoom, format x-y> <needs translating>

set ARG1=%1
set ARG2=%2
set ARG3=%3

rem set up environment for gdal
set OSGEO4W_ROOT=Z:\Programs\OSGeo4W
PATH=%OSGEO4W_ROOT%\bin;%PATH%
for %%f in (%OSGEO4W_ROOT%\etc\ini\*.bat) do call %%f
call Z:\Programs\OSGeo4W\bin\gdal16.bat

if "%ARG3%"=="nogeonotranslate" GOTO NOTRANSLATE
if "%ARG3%"=="geonotranslate" GOTO GEONOTRANSLATE

rem do processing

gdal_translate -of vrt -expand rgba %ARG1% temp.vrt
gdal2tiles -f jpeg -z %ARG2% -a 0 temp.vrt
GOTO END

rem process non-georeferenced files
:NOTRANSLATE
gdal2tiles -p raster -f jpeg -z %ARG2% -a 0 %ARG1%
GOTO END

rem process georeferenced tiffs that don't need the color space mumbo jumbo
:GEONOTRANSLATE
gdal2tiles -f jpeg -z %ARG2% -a 0 %ARG1%
GOTO END

:END
