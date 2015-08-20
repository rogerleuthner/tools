# tools

# OpenFlightGPS Companion Tools (ofg)
Map processing.  Pulls from FAA Digital Products website, then processes for us in OpenFlightGPS.

Copy these tools into a 'bin' subdirectory where you want your products to be created.

Very brittle; would like to convert to using @jlmcgraw tools which are much better written, and also offer contiguous charts rather than those exactly reflecting the FAA distributed section charts - but that's a major project, and will require an OpenFlightGPS re-write.

## Requirements
* cygwin (easy port to any *nix flavor); needs wget etc.
* Imagemagik
* gdal installed into C:\OSGeo4W
* 7zip
* More to come

