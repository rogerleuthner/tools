# tools

# OpenFlightGPS Companion Tools (ofg)
Map processing.  Pulls from FAA Digital Products website, then processes for use in OpenFlightGPS.

Very brittle; would like to convert to using @jlmcgraw tools which are much better written, and also offer contiguous charts rather than those exactly reflecting the FAA distributed section charts - but that's a major project, and will require an OpenFlightGPS re-write.

# TODO
Update extremely slow gdal2tiles.py to take advantage of newer gdal multi-core.  These scripts are a hackaround and do 'multi-core' processing only by kicking off several parallel download/processing jobs, each of which process a single file at a time.

## Requirements
* cygwin (easy port to any *nix flavor); needs wget etc.
* Imagemagik
* gdal installed such that gdal2tiles.py will execute (e.g. correct python linkage); this was tricky a few years ago and accomplished via install of OSGeo4W, but probably is now simple
* 7zip
* More to come

## Windows Installation
* Overwrite Z:\Programs\OSGeo4W\gdal2tiles.py with this version
* Copy remaining tools into a 'bin' subdirectory where you want your products to be created
* Copy into that bin directory files: 7z.dll, 7z.exe, 7z.sfx, 7zCon.sfx, 7zFM.exe, 7-zip.dll
* Create subdirectory bin/ImageMagick-6.8.6-10 and copy whole ImageMagick installation
