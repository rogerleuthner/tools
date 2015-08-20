#!/bin/sh

## $1 is the 'inline' from caller

 # /*******************************************************************************
 #  * Copyright 2009-2015 by Roger B. Leuthner
 #  *
 #  * This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
 #  * without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 #  * GNU General Public License for more details.
 #  *
 #  * Commercial Distribution License
 #  * If you would like to distribute OpenFlightGPS (or portions thereof) under a license other than
 #  * the "GNU General Public License, version 2", contact Roger B. Leuthner through GitHub.
 #  *
 #  * GNU Public License, version 2
 #  * All distribution of OpenFlightGPS must conform to the terms of the GNU Public License, version 2.
 #  ******************************************************************************/

# get the filename, expand the zip into directory sans ".zip" part
inline="${1}"
FILENAME=`echo $inline | sed 's/.*\///g'`    
UNZIPDIR=`echo $FILENAME | sed 's/.zip//'`

# get the file
wget $inline

mkdir ${UNZIPDIR}
7z e -o${UNZIPDIR} $FILENAME
cd ${UNZIPDIR}

# this should only be a single .tif
tifname=`ls *.tif`

PRODUCT="`echo $tifname | sed 's/ .*//'`"
GEOREF="true"
METADATA_TMP_FILE="`echo $tifname | sed 's/.tif/.htm/'`"

# process with non-space-containing filename
mv *.tif ${PRODUCT}.tif            

GDAL.bat ${PRODUCT}.tif $ZOOMS $GEOREF
cd temp

# reduce the size by about 1/2 
find . -type f -name \*.jpg -print | while read cvtline
do
    convert -quality 45 $cvtline $cvtline
done    

# clean out some garbage left by 2tiles
rm -f googlemaps.html openlayers.html

# rename to our suffix
find . -name \*.jpg | while read jpgline
do 
    mv ${jpgline} `echo $jpgline | sed 's/.jpg/.ofm/'`
done    

# copy in the metadata descriptor (and give it a universal name)
cp "../${METADATA_TMP_FILE}" $MAP_METADATA_FILE

# create product .zip file
7z a ../../../${PRODUCT}.zip *

# cleanup
cd ..                
mv ${PRODUCT}.tif "$tifname"
rm -rf temp*
rm -rf ${PRODUCT}    


    



