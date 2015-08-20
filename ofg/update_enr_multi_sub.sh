#!/bin/sh

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

## $1 is the 'inline' from caller
	
# get the filename, expand the zip into directory sans ".zip" part
export inline="${1}"
FILENAME=`echo $inline | sed 's/.*\///g'`	
UNZIPDIR=`echo $FILENAME | sed 's/.zip//'`

# get the file
wget $inline

mkdir ${UNZIPDIR}
7z e -o${UNZIPDIR} $FILENAME
cd ${UNZIPDIR}

ls *.tif | while read tifname
do
	# ENR_L12.tif --> L12.tif
	PRODUCT=`echo $tifname | sed -e 's/ENR_//' -e 's/.tif//'`
	METADATA_TMP_FILE="`echo $tifname | sed 's/.tif/_tif.htm/'`"

	# process with non-space-containing filename, and restore the file to it's original name
	mv "$tifname" ${PRODUCT}.tif			
	
	# file, no translate
	GDAL.bat ${PRODUCT}.tif $ZOOMS geonotranslate
	
	cd ${PRODUCT}
	
	# reduce the size by about 1/2 
	find . -type f -name \*.jpg -print | while read cvtline
	do
		convert -quality 25 $cvtline $cvtline
	done			
	
	# clean out some garbage left by 2tiles
	rm -f googlemaps.html openlayers.html
	
	find . -name \*.jpg | while read jpgline
	do 
		mv ${jpgline} `echo $jpgline | sed 's/.jpg/.ofm/'`
	done


	
	# manually build the xml file since it doesn't have the required attributes
	# for geo, and the expiry dates are in the urls
	DATA=`grep West_Bounding_Coordinate ../${METADATA_TMP_FILE} | sed -e 's/.*em>//' -e 's/ //g' -e 's/<\/dt>//'`
	echo "dc.coverage.x.min=${DATA}" > $MAP_METADATA_FILE
	DATA=`grep East_Bounding_Coordinate ../${METADATA_TMP_FILE} | sed -e 's/.*em>//' -e 's/ //g' -e 's/<\/dt>//'`
	echo "dc.coverage.x.max=${DATA}" >> $MAP_METADATA_FILE
	DATA=`grep North_Bounding_Coordinate ../${METADATA_TMP_FILE} | sed -e 's/.*em>//' -e 's/ //g' -e 's/<\/dt>//'`
	echo "dc.coverage.y.max=${DATA}" >> $MAP_METADATA_FILE
	DATA=`grep South_Bounding_Coordinate ../${METADATA_TMP_FILE} | sed -e 's/.*em>//' -e 's/ //g' -e 's/<\/dt>//'`
	echo "dc.coverage.y.min=${DATA}" >> $MAP_METADATA_FILE		
	echo "dc.coverage.t.min=${DATE_EFF}" >> $MAP_METADATA_FILE	
	echo "dc.coverage.t.max=${DATE_EXP}" >> $MAP_METADATA_FILE		
	
	# create product .zip file
	7z a ../../../${PRODUCT}.zip *
	
	# cleanup
	cd ..				
	mv ${PRODUCT}.tif "$tifname"
	rm -rf ${PRODUCT}
	
done

	



