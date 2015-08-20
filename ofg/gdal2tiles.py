#!/usr/bin/env python
# NOTE!! This is not the original version distributed with the OSGeo4W!! It has been modified to work with OpenFlightGPS.
# FORK SOURCE VERSION:
# http://code.google.com/p/maptiler/source/browse/trunk/maptiler/gdal2tiles.py
# on 11/27/2010.
# (1/3/2011) Edited to generate the correct tile names, no reversing necessary.
#     Thanks Erik Burrows!
#******************************************************************************
#  $Id: gdal2tiles.py 15748 2008-11-17 16:30:54Z klokan $
# 
# Project:  Google Summer of Code 2007, 2008 (http://code.google.com/soc/)
# Support:  BRGM (http://www.brgm.fr)
# Purpose:  Convert a raster into TMS (Tile Map Service) tiles in a directory.
#           - generate Google Earth metadata (KML SuperOverlay)
#           - generate simple HTML viewer based on Google Maps and OpenLayers
#           - support of global tiles (Spherical Mercator) for compatibility
#               with interactive web maps a la Google Maps
# Author:   Klokan Petr Pridal, klokan at klokan dot cz
# Web:      http://www.klokan.cz/projects/gdal2tiles/
# GUI:      http://www.maptiler.org/
#
###############################################################################
# Copyright (c) 2008, Klokan Petr Pridal
# 
#  Permission is hereby granted, free of charge, to any person obtaining a
#  copy of this software and associated documentation files (the "Software"),
#  to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense,
#  and/or sell copies of the Software, and to permit persons to whom the
#  Software is furnished to do so, subject to the following conditions:
# 
#  The above copyright notice and this permission notice shall be included
#  in all copies or substantial portions of the Software.
# 
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#  OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
#  THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.
#******************************************************************************

from osgeo import gdal
from osgeo import osr

import sys
import os
import math

try:
        from PIL import Image
        import numpy
        import osgeo.gdal_array as gdalarray
except:
        # 'antialias' resampling is not available
        pass

__version__ = "$Id: gdal2tiles.py 15748 2008-11-17 16:30:54Z klokan $"

resampling_list = ('average','near','bilinear','cubic','cubicspline','lanczos','antialias')
tile_formats_list = ('png', 'jpeg', 'hybrid')
profile_list = ('mercator','geodetic','raster','gearth') #,'zoomify')
webviewer_list = ('all','google','openlayers','none')

format_extension = {
        "PNG" : "png",
        "JPEG" : "jpg"
}

format_mime = {
        "PNG" : "image/png",
        "JPEG" : "image/jpeg"
}

# =============================================================================
# =============================================================================
# =============================================================================

__doc__globalmaptiles = """
globalmaptiles.py

Global Map Tiles as defined in Tile Map Service (TMS) Profiles
==============================================================

Functions necessary for generation of global tiles used on the web.
It contains classes implementing coordinate conversions for:

  - GlobalMercator (based on EPSG:900913 = EPSG:3785)
       for Google Maps, Yahoo Maps, Microsoft Maps compatible tiles
  - GlobalGeodetic (based on EPSG:4326)
       for OpenLayers Base Map and Google Earth compatible tiles

More info at:

http://wiki.osgeo.org/wiki/Tile_Map_Service_Specification
http://wiki.osgeo.org/wiki/WMS_Tiling_Client_Recommendation
http://msdn.microsoft.com/en-us/library/bb259689.aspx
http://code.google.com/apis/maps/documentation/overlays.html#Google_Maps_Coordinates

Created by Klokan Petr Pridal on 2008-07-03.
Google Summer of Code 2008, project GDAL2Tiles for OSGEO.

In case you use this class in your product, translate it to another language
or find it usefull for your project please let me know.
My email: klokan at klokan dot cz.
I would like to know where it was used.

Class is available under the open-source GDAL license (www.gdal.org).
"""

import math

MAXZOOMLEVEL = 32

class GlobalMercator(object):
        """
        TMS Global Mercator Profile
        ---------------------------

        Functions necessary for generation of tiles in Spherical Mercator projection,
        EPSG:900913 (EPSG:gOOglE, Google Maps Global Mercator), EPSG:3785, OSGEO:41001.

        Such tiles are compatible with Google Maps, Microsoft Virtual Earth, Yahoo Maps,
        UK Ordnance Survey OpenSpace API, ...
        and you can overlay them on top of base maps of those web mapping applications.
        
        Pixel and tile coordinates are in TMS notation (origin [0,0] in bottom-left).

        What coordinate conversions do we need for TMS Global Mercator tiles::

             LatLon      <->       Meters      <->     Pixels    <->       Tile     

         WGS84 coordinates   Spherical Mercator  Pixels in pyramid  Tiles in pyramid
             lat/lon            XY in metres     XY pixels Z zoom      XYZ from TMS 
            EPSG:4326           EPSG:900913                                         
             .----.              ---------               --                TMS      
            /      \     <->     |       |     <->     /----/    <->      Google    
            \      /             |       |           /--------/          QuadTree   
             -----               ---------         /------------/                   
           KML, public         WebMapService         Web Clients      TileMapService

        What is the coordinate extent of Earth in EPSG:900913?

          [-20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244]
          Constant 20037508.342789244 comes from the circumference of the Earth in meters,
          which is 40 thousand kilometers, the coordinate origin is in the middle of extent.
      In fact you can calculate the constant as: 2 * math.pi * 6378137 / 2.0
          $ echo 180 85 | gdaltransform -s_srs EPSG:4326 -t_srs EPSG:900913
          Polar areas with abs(latitude) bigger then 85.05112878 are clipped off.

        What are zoom level constants (pixels/meter) for pyramid with EPSG:900913?

          whole region is on top of pyramid (zoom=0) covered by 512x512 pixels tile,
          every lower zoom level resolution is always divided by two
          initialResolution = 20037508.342789244 * 2 / 512 = 156543.03392804062

        What is the difference between TMS and Google Maps/QuadTree tile name convention?

          The tile raster itself is the same (equal extent, projection, pixel size),
          there is just different identification of the same raster tile.
          Tiles in TMS are counted from [0,0] in the bottom-left corner, id is XYZ.
          Google placed the origin [0,0] to the top-left corner, reference is XYZ.
          Microsoft is referencing tiles by a QuadTree name, defined on the website:
          http://msdn2.microsoft.com/en-us/library/bb259689.aspx

        The lat/lon coordinates are using WGS84 datum, yeh?

          Yes, all lat/lon we are mentioning should use WGS84 Geodetic Datum.
          Well, the web clients like Google Maps are projecting those coordinates by
          Spherical Mercator, so in fact lat/lon coordinates on sphere are treated as if
          the were on the WGS84 ellipsoid.
         
          From MSDN documentation:
          To simplify the calculations, we use the spherical form of projection, not
          the ellipsoidal form. Since the projection is used only for map display,
          and not for displaying numeric coordinates, we don't need the extra precision
          of an ellipsoidal projection. The spherical projection causes approximately
          0.33 percent scale distortion in the Y direction, which is not visually noticable.

        How do I create a raster in EPSG:900913 and convert coordinates with PROJ.4?

          You can use standard GIS tools like gdalwarp, cs2cs or gdaltransform.
          All of the tools supports -t_srs 'epsg:900913'.

          For other GIS programs check the exact definition of the projection:
          More info at http://spatialreference.org/ref/user/google-projection/
          The same projection is degined as EPSG:3785. WKT definition is in the official
          EPSG database.

          Proj4 Text:
            +proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0
            +k=1.0 +units=m +nadgrids=@null +no_defs

          Human readable WKT format of EPGS:900913:
             PROJCS["Google Maps Global Mercator",
                 GEOGCS["WGS 84",
                     DATUM["WGS_1984",
                         SPHEROID["WGS 84",6378137,298.2572235630016,
                             AUTHORITY["EPSG","7030"]],
                         AUTHORITY["EPSG","6326"]],
                     PRIMEM["Greenwich",0],
                     UNIT["degree",0.0174532925199433],
                     AUTHORITY["EPSG","4326"]],
                 PROJECTION["Mercator_1SP"],
                 PARAMETER["central_meridian",0],
                 PARAMETER["scale_factor",1],
                 PARAMETER["false_easting",0],
                 PARAMETER["false_northing",0],
                 UNIT["metre",1,
                     AUTHORITY["EPSG","9001"]]]
        """

        def __init__(self, tileSize=512):
                "Initialize the TMS Global Mercator pyramid"
                self.tileSize = tileSize
                self.initialResolution = 2 * math.pi * 6378137 / self.tileSize
                # 156543.03392804062 for tileSize 512 pixels
                self.originShift = 2 * math.pi * 6378137 / 2.0
                # 20037508.342789244

        def LatLonToMeters(self, lat, lon ):
                "Converts given lat/lon in WGS84 Datum to XY in Spherical Mercator EPSG:900913"

                mx = lon * self.originShift / 180.0
                my = math.log( math.tan((90 + lat) * math.pi / 360.0 )) / (math.pi / 180.0)

                my = my * self.originShift / 180.0
                return mx, my

        def MetersToLatLon(self, mx, my ):
                "Converts XY point from Spherical Mercator EPSG:900913 to lat/lon in WGS84 Datum"

                lon = (mx / self.originShift) * 180.0
                lat = (my / self.originShift) * 180.0

                lat = 180 / math.pi * (2 * math.atan( math.exp( lat * math.pi / 180.0)) - math.pi / 2.0)
                return lat, lon

        def PixelsToMeters(self, px, py, zoom):
                "Converts pixel coordinates in given zoom level of pyramid to EPSG:900913"

                res = self.Resolution( zoom )
                mx = px * res - self.originShift
                my = py * res - self.originShift
                return mx, my
                
        def MetersToPixels(self, mx, my, zoom):
                "Converts EPSG:900913 to pyramid pixel coordinates in given zoom level"
                                
                res = self.Resolution( zoom )
                px = (mx + self.originShift) / res
                py = (my + self.originShift) / res
                return px, py
        
        def PixelsToTile(self, px, py):
                "Returns a tile covering region in given pixel coordinates"

                tx = int( math.ceil( px / float(self.tileSize) ) - 1 )
                ty = int( math.ceil( py / float(self.tileSize) ) - 1 )
                return tx, ty

        def PixelsToRaster(self, px, py, zoom):
                "Move the origin of pixel coordinates to top-left corner"
                
                mapSize = self.tileSize << zoom
                return px, mapSize - py
                
        def MetersToTile(self, mx, my, zoom):
                "Returns tile for given mercator coordinates"
                
                px, py = self.MetersToPixels( mx, my, zoom)
                return self.PixelsToTile( px, py)

        def TileBounds(self, tx, ty, zoom):
                "Returns bounds of the given tile in EPSG:900913 coordinates"
                
                minx, miny = self.PixelsToMeters( tx*self.tileSize, ty*self.tileSize, zoom )
                maxx, maxy = self.PixelsToMeters( (tx+1)*self.tileSize, (ty+1)*self.tileSize, zoom )
                return ( minx, miny, maxx, maxy )

        def TileLatLonBounds(self, tx, ty, zoom ):
                "Returns bounds of the given tile in latutude/longitude using WGS84 datum"

                bounds = self.TileBounds( tx, ty, zoom)
                minLat, minLon = self.MetersToLatLon(bounds[0], bounds[1])
                maxLat, maxLon = self.MetersToLatLon(bounds[2], bounds[3])
                 
                return ( minLat, minLon, maxLat, maxLon )
                
        def Resolution(self, zoom ):
                "Resolution (meters/pixel) for given zoom level (measured at Equator)"
                
                # return (2 * math.pi * 6378137) / (self.tileSize * 2**zoom)
                return self.initialResolution / (2**zoom)
                
        def ZoomForPixelSize(self, pixelSize ):
                "Maximal scaledown zoom of the pyramid closest to the pixelSize."
                
                for i in range(MAXZOOMLEVEL):
                        if pixelSize > self.Resolution(i):
                                if i!=0:
                                        return i-1
                                else:
                                        return 0 # We don't want to scale up
                
        def GoogleTile(self, tx, ty, zoom):
                "Converts TMS tile coordinates to Google Tile coordinates"
                
                # coordinate origin is moved from bottom-left to top-left corner of the extent
                return tx, (2**zoom - 1) - ty

        def QuadTree(self, tx, ty, zoom ):
                "Converts TMS tile coordinates to Microsoft QuadTree"
                
                quadKey = ""
                ty = (2**zoom - 1) - ty
                for i in range(zoom, 0, -1):
                        digit = 0
                        mask = 1 << (i-1)
                        if (tx & mask) != 0:
                                digit += 1
                        if (ty & mask) != 0:
                                digit += 2
                        quadKey += str(digit)
                        
                return quadKey

#---------------------

class GlobalGeodetic(object):
        """
        TMS Global Geodetic Profile
        ---------------------------

        Functions necessary for generation of global tiles in Plate Carre projection,
        EPSG:4326, "unprojected profile".

        Such tiles are compatible with Google Earth (as any other EPSG:4326 rasters)
        and you can overlay the tiles on top of OpenLayers base map.
        
        Pixel and tile coordinates are in TMS notation (origin [0,0] in bottom-left).

        What coordinate conversions do we need for TMS Global Geodetic tiles?

          Global Geodetic tiles are using geodetic coordinates (latitude,longitude)
          directly as planar coordinates XY (it is also called Unprojected or Plate
          Carre). We need only scaling to pixel pyramid and cutting to tiles.
          Pyramid has on top level two tiles, so it is not square but rectangle.
          Area [-180,-90,180,90] is scaled to 512x512 pixels.
          TMS has coordinate origin (for pixels and tiles) in bottom-left corner.
          Rasters are in EPSG:4326 and therefore are compatible with Google Earth.

             LatLon      <->      Pixels      <->     Tiles     

         WGS84 coordinates   Pixels in pyramid  Tiles in pyramid
             lat/lon         XY pixels Z zoom      XYZ from TMS 
            EPSG:4326                                           
             .----.                ----                         
            /      \     <->    /--------/    <->      TMS      
            \      /         /--------------/                   
             -----        /--------------------/                
           WMS, KML    Web Clients, Google Earth  TileMapService
        """

        def __init__(self, tileSize = 512):
                self.tileSize = tileSize

        def LatLonToPixels(self, lat, lon, zoom):
                "Converts lat/lon to pixel coordinates in given zoom of the EPSG:4326 pyramid"

                res = 180.0 / self.tileSize / 2**zoom
                px = (180 + lat) / res
                py = (90 + lon) / res
                return px, py

        def PixelsToTile(self, px, py):
                "Returns coordinates of the tile covering region in pixel coordinates"

                tx = int( math.ceil( px / float(self.tileSize) ) - 1 )
                ty = int( math.ceil( py / float(self.tileSize) ) - 1 )
                return tx, ty
        
        def LatLonToTile(self, lat, lon, zoom):
                "Returns the tile for zoom which covers given lat/lon coordinates"
                
                px, py = self.LatLonToPixels( lat, lon, zoom)
                return self.PixelsToTile(px,py)

        def Resolution(self, zoom ):
                "Resolution (arc/pixel) for given zoom level (measured at Equator)"
                
                return 180.0 / self.tileSize / 2**zoom
                #return 180 / float( 1 << (8+zoom) )
                
        def ZoomForPixelSize(self, pixelSize ):
                "Maximal scaledown zoom of the pyramid closest to the pixelSize."

                for i in range(MAXZOOMLEVEL):
                        if pixelSize > self.Resolution(i):
                                if i!=0:
                                        return i-1
                                else:
                                        return 0 # We don't want to scale up

        def TileBounds(self, tx, ty, zoom):
                "Returns bounds of the given tile"
                res = 180.0 / self.tileSize / 2**zoom
                return (
                        tx*self.tileSize*res - 180,
                        ty*self.tileSize*res - 90,
                        (tx+1)*self.tileSize*res - 180,
                        (ty+1)*self.tileSize*res - 90
                )
                
        def TileLatLonBounds(self, tx, ty, zoom):
                "Returns bounds of the given tile in the SWNE form"
                b = self.TileBounds(tx, ty, zoom)
                return (b[1],b[0],b[3],b[2])

# =============================================================================


class GDAL2Tiles(object):

        # -------------------------------------------------------------------------
        def process(self):
                """The main processing function, runs all the main steps of processing"""
                
                # Opening and preprocessing of the input file
                self.open_input()

                # Generation of main metadata files and HTML viewers
                self.generate_metadata()
                
                # Generation of the lowest tiles
                self.generate_base_tiles()
                
                # Generation of the overview tiles (higher in the pyramid)
                self.generate_overview_tiles()
                
        # -------------------------------------------------------------------------
        def error(self, msg, details = "" ):
                """Print an error message and stop the processing"""

                if details:
                        self.parser.error(msg + "\n\n" + details)
                else:   
                        self.parser.error(msg)
                
        # -------------------------------------------------------------------------
        def progressbar(self, complete = 0.0):
                """Print progressbar for float value 0..1"""
                
                gdal.TermProgress_nocb(complete)

        # -------------------------------------------------------------------------
        def stop(self):
                """Stop the rendering immediately"""
                self.stopped = True

        # -------------------------------------------------------------------------
        def __init__(self, arguments ):
                """Constructor function - initialization"""
                
                self.stopped = False
                self.input = None
                self.output = None

                # Tile format
                self.tilesize = 512

                # Should we read bigger window of the input raster and scale it down?
                # Note: Modified leter by open_input()
                # Not for 'near' resampling
                # Not for Wavelet based drivers (JPEG2000, ECW, MrSID)
                # Not for 'raster' profile
                self.scaledquery = True
                # How big should be query window be for scaling down
                # Later on reset according the chosen resampling algorightm
                self.querysize = 4 * self.tilesize

                # Should we use Read on the input file for generating overview tiles?
                # Note: Modified later by open_input()
                # Otherwise the overview tiles are generated from existing underlying tiles
                self.overviewquery = False
                
                # RUN THE ARGUMENT PARSER:
                
                self.optparse_init()
                self.options, self.args = self.parser.parse_args(args=arguments)
                if not self.args:
                        self.error("No input file specified")

                # POSTPROCESSING OF PARSED ARGUMENTS:

                # Workaround for old versions of GDAL
                try:
                        if (self.options.verbose and self.options.resampling == 'near') or gdal.TermProgress_nocb:
                                pass
                except:
                        self.error("This version of GDAL is not supported. Please upgrade to 1.6+.")
                        #,"You can try run crippled version of gdal2tiles with parameters: -v -r 'near'")
                
                # Is output directory the last argument?

                # Test output directory, if it doesn't exist
                if os.path.isdir(self.args[-1]) or ( len(self.args) > 1 and not os.path.exists(self.args[-1])):
                        self.output = self.args[-1]
                        self.args = self.args[:-1]

                # More files on the input not directly supported yet
                
                if (len(self.args) > 1):
                        self.error("Processing of several input files is not supported.",
                        """Please first use a tool like gdal_vrtmerge.py or gdal_merge.py on the files:
gdal_vrtmerge.py -o merged.vrt %s""" % " ".join(self.args))
                        # TODO: Call functions from gdal_vrtmerge.py directly
                        
                self.input = self.args[0]
                
                # Default values for not given options
                
                if not self.output:
                        # Directory with input filename without extension in actual directory
                        self.output = os.path.splitext(os.path.basename( self.input ))[0]
                                
                if not self.options.title:
                        self.options.title = os.path.basename( self.input )

                if self.options.url and not self.options.url.endswith('/'):
                        self.options.url += '/'
                if self.options.url:
                        self.options.url += os.path.basename( self.output ) + '/'

                # Supported options
                
                if self.options.resampling == 'average':
                        try:
                                if gdal.RegenerateOverview:
                                        pass
                        except:
                                self.error("'average' resampling algorithm is not available.", "Please use -r 'near' argument or upgrade to newer version of GDAL.")
                
                elif self.options.resampling == 'antialias':
                        try:
                                if numpy:
                                        pass
                        except:
                                self.error("'antialias' resampling algorithm is not available.", "Install PIL (Python Imaging Library) and numpy.")
                
                elif self.options.resampling == 'near':
                        self.querysize = self.tilesize
                elif self.options.resampling == 'bilinear':
                        self.querysize = self.tilesize * 2

                # Tile format.
                if self.options.tile_format is None:
                        if self.options.profile == 'gearth':
                                self.options.tile_format = 'hybrid'
                        else:
                                self.options.tile_format = 'png'


				self.options.webviewer = 'none'

                # User specified zoom levels
                self.tminz = None
                self.tmaxz = None
                if self.options.zoom:
                        minmax = self.options.zoom.split('-',1)
                        minmax.extend([''])
                        min, max = minmax[:2]
                        self.tminz = int(min)
                        if max:
                                self.tmaxz = int(max)
                        else:
                                self.tmaxz = int(min) 
                


                # Output the results

                if self.options.verbose:
                        print "Options:", self.options
                        print "Input:", self.input
                        print "Output:", self.output
                        print "Cache: %s MB" % (gdal.GetCacheMax() / 1024 / 1024)
                        print

        # -------------------------------------------------------------------------
        def optparse_init(self):
                """Prepare the option parser for input (argv)"""
                
                from optparse import OptionParser, OptionGroup
                usage = "Usage: %prog [options] input_file(s) [output]"
                p = OptionParser(usage, version="%prog "+ __version__)
                p.add_option("-p", "--profile", dest='profile', type='choice', choices=profile_list,
                                                  help="Tile cutting profile (%s) - default 'mercator' (Google Maps compatible)" % ",".join(profile_list))
                p.add_option("-r", "--resampling", dest="resampling", type='choice', choices=resampling_list,
                                                help="Resampling method (%s) - default 'average'" % ",".join(resampling_list))
                p.add_option("-f", "--tile-format", dest="tile_format", type='choice', choices=tile_formats_list,
                                                help="Image format of generated tiles (%s) - default 'png'" % ",".join(tile_formats_list))
                p.add_option('-s', '--s_srs', dest="s_srs", metavar="SRS",
                                                  help="The spatial reference system used for the source input data")
                p.add_option('-z', '--zoom', dest="zoom",
                                                  help="Zoom levels to render (format:'2-5' or '10').")
                p.add_option('-e', '--resume', dest="resume", action="store_true",
                                                  help="Resume mode. Generate only missing files.")
                p.add_option('-a', '--srcnodata', dest="srcnodata", metavar="NODATA",
                                                  help="NODATA transparency value to assign to the input data")
                p.add_option("-v", "--verbose",
                                                  action="store_true", dest="verbose",
                                                  help="Print status messages to stdout")

                # KML options 
                g = OptionGroup(p, "KML (Google Earth) options", "Options for generated Google Earth SuperOverlay metadata")
                g.add_option("-k", "--force-kml", dest='kml', action="store_true",
                                                  help="Generate KML for Google Earth - default for 'geodetic' profile and 'raster' in EPSG:4326. For a dataset with different projection use with caution!")
                g.add_option("-n", "--no-kml", dest='kml', action="store_false",
                                                  help="Avoid automatic generation of KML files for EPSG:4326")
                g.add_option("-u", "--url", dest='url',
                                                  help="URL address where the generated tiles are going to be published")
                g.add_option('-d', '--kml-depth', dest="kml_depth",
                                                  help="How many levels to store before linking, default 1.")
                p.add_option_group(g)

                # HTML options
                g = OptionGroup(p, "Web viewer options", "Options for generated HTML viewers a la Google Maps")
                g.add_option("-w", "--webviewer", dest='webviewer', type='choice', choices=webviewer_list,
                                                  help="Web viewer to generate (%s) - default 'all'" % ",".join(webviewer_list))
                g.add_option("-t", "--title", dest='title',
                                                  help="Title of the map")
                g.add_option("-c", "--copyright", dest='copyright',
                                                  help="Copyright for the map")
                g.add_option("-g", "--googlekey", dest='googlekey',
                                                  help="Google Maps API key from http://code.google.com/apis/maps/signup.html")
                g.add_option("-y", "--yahookey", dest='yahookey',
                                                  help="Yahoo Application ID from http://developer.yahoo.com/wsregapp/")
                p.add_option_group(g)
                
                # TODO: MapFile + TileIndexes per zoom level for efficient MapServer WMS
                #g = OptionGroup(p, "WMS MapServer metadata", "Options for generated mapfile and tileindexes for MapServer")
                #g.add_option("-i", "--tileindex", dest='wms', action="store_true"
                #                                 help="Generate tileindex and mapfile for MapServer (WMS)")
                # p.add_option_group(g)

                p.set_defaults(verbose=False, profile="mercator", kml=False, url='',
                copyright='', resampling='average', resume=False,
                googlekey='INSERT_YOUR_KEY_HERE', yahookey='INSERT_YOUR_YAHOO_APP_ID_HERE')

                self.parser = p
                



        # -------------------------------------------------------------------------
        def open_input(self):
                """Initialization of the input raster, reprojection if necessary"""
                
                gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")
                gdal.AllRegister()

                # Open the input file
                if self.input:
                        self.in_ds = gdal.Open(self.input, gdal.GA_ReadOnly)
                else:
                        raise Exception("No input file was specified")

                if self.options.verbose:
                        print "Input file:", "( %sP x %sL - %s bands)" % (self.in_ds.RasterXSize, self.in_ds.RasterYSize, self.in_ds.RasterCount)

                if not self.in_ds:
                        # Note: GDAL prints the ERROR message too
                        self.error("It is not possible to open the input file '%s'." % self.input )
                        
                # Read metadata from the input file
                if self.in_ds.RasterCount == 0:
                        self.error( "Input file '%s' has no raster band" % self.input )
                        
                if self.in_ds.GetRasterBand(1).GetRasterColorTable():
                        # TODO: Process directly paletted dataset by generating VRT in memory
                        self.error( "Please convert this file to RGB/RGBA and run gdal2tiles on the result.",
                        """From paletted file you can create RGBA file (temp.vrt) by:
gdal_translate -of vrt -expand rgba %s temp.vrt
then run:
gdal2tiles temp.vrt""" % self.input )

                # Get NODATA value
                # User supplied values overwrite everything else.
                if self.options.srcnodata:
                        nds = map( float, self.options.srcnodata.split(','))
                        if len(nds) < self.in_ds.RasterCount:
                                self.in_nodata = (nds * self.in_ds.RasterCount)[:self.in_ds.RasterCount]
                        else:
                                self.in_nodata = nds
                else:
                        # If the source dataset has NODATA, use it.
                        self.in_nodata = []
                        for i in range(1, self.in_ds.RasterCount+1):
                                if self.in_ds.GetRasterBand(i).GetNoDataValue() != None:
                                        self.in_nodata.append( self.in_ds.GetRasterBand(i).GetNoDataValue() )

                        # If it does not and we are producing JPEG, make NODATA white.
                        if len(self.in_nodata) == 0 and self.options.tile_format == "jpeg":
                                if self.in_ds.RasterCount in (1,3):
                                        self.in_nodata = [255] * self.in_ds.RasterCount
                                elif self.in_ds.RasterCount == 4:
                                        self.in_nodata = [255,255,255,0]

                if self.options.verbose:
                        print "NODATA: %s" % self.in_nodata

                #
                # Here we should have RGBA input dataset opened in self.in_ds
                #

                if self.options.verbose:
                        print "Preprocessed file:", "( %sP x %sL - %s bands)" % (self.in_ds.RasterXSize, self.in_ds.RasterYSize, self.in_ds.RasterCount)

                # Spatial Reference System of the input raster


                self.in_srs = None
                
                if self.options.s_srs:
                        self.in_srs = osr.SpatialReference()
                        self.in_srs.SetFromUserInput(self.options.s_srs)
                        self.in_srs_wkt = self.in_srs.ExportToWkt()
                else:
                        self.in_srs_wkt = self.in_ds.GetProjection()
                        if not self.in_srs_wkt and self.in_ds.GetGCPCount() != 0:
                                self.in_srs_wkt = self.in_ds.GetGCPProjection()
                        if self.in_srs_wkt:
                                self.in_srs = osr.SpatialReference()
                                self.in_srs.ImportFromWkt(self.in_srs_wkt)
                        #elif self.options.profile != 'raster':
                        #       self.error("There is no spatial reference system info included in the input file.","You should run gdal2tiles with --s_srs EPSG:XXXX or similar.")

                # Spatial Reference System of tiles
                
                self.out_srs = osr.SpatialReference()

                if self.options.profile == 'mercator':
                        self.out_srs.ImportFromEPSG(900913)
                elif self.options.profile in ('geodetic', 'gearth'):
                        self.out_srs.ImportFromEPSG(4326)
                else:
                        self.out_srs = self.in_srs
                
                # Are the reference systems the same? Reproject if necessary.

                self.out_ds = None
                
                if self.options.profile in ('mercator', 'geodetic', 'gearth'):
                                                
                        if (self.in_ds.GetGeoTransform() == (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)) and (self.in_ds.GetGCPCount() == 0):
                                self.error("There is no georeference - neither affine transformation (worldfile) nor GCPs. You can generate only 'raster' profile tiles.",
                                "Either gdal2tiles with parameter -p 'raster' or use another GIS software for georeference e.g. gdal_transform -gcp / -a_ullr / -a_srs")
                                
                        if self.in_srs:
                                
                                if (self.in_srs.ExportToProj4() != self.out_srs.ExportToProj4()) or (self.in_ds.GetGCPCount() != 0):
                                        
                                        # Generation of VRT dataset in tile projection, default 'nearest neighbour' warping
                                        self.out_ds = gdal.AutoCreateWarpedVRT( self.in_ds, self.in_srs_wkt, self.out_srs.ExportToWkt() )
                                        
                                        # TODO: HIGH PRIORITY: Correction of AutoCreateWarpedVRT according the max zoomlevel for correct direct warping!!!
                                        
                                        if self.options.verbose:
                                                print "Warping of the raster by AutoCreateWarpedVRT (result saved into 'tiles.vrt')"
                                                self.out_ds.GetDriver().CreateCopy("tiles.vrt", self.out_ds)
                                                
                                        # Note: self.in_srs and self.in_srs_wkt contain still the non-warped reference system!!!

                                        # Correction of AutoCreateWarpedVRT for NODATA values
                                        if self.in_nodata != []:
                                                import tempfile
                                                tempfilename = tempfile.mktemp('-gdal2tiles.vrt')
                                                self.out_ds.GetDriver().CreateCopy(tempfilename, self.out_ds)
                                                # open as a text file
                                                s = open(tempfilename).read()
                                                # Add the warping options
                                                s = s.replace("""<GDALWarpOptions>""","""<GDALWarpOptions>
          <Option name="INIT_DEST">NO_DATA</Option>
          <Option name="UNIFIED_SRC_NODATA">YES</Option>""")
                                                # replace BandMapping tag for NODATA bands....
                                                for i in range(len(self.in_nodata)):
                                                        s = s.replace("""<BandMapping src="%i" dst="%i"/>""" % ((i+1),(i+1)),"""<BandMapping src="%i" dst="%i">
              <SrcNoDataReal>%i</SrcNoDataReal>
              <SrcNoDataImag>0</SrcNoDataImag>
              <DstNoDataReal>%i</DstNoDataReal>
              <DstNoDataImag>0</DstNoDataImag>
            </BandMapping>""" % ((i+1), (i+1), self.in_nodata[i], self.in_nodata[i])) # Or rewrite to white by: , 255 ))
                                                # save the corrected VRT
                                                open(tempfilename,"w").write(s)
                                                # open by GDAL as self.out_ds
                                                self.out_ds = gdal.Open(tempfilename) #, gdal.GA_ReadOnly)
                                                # delete the temporary file
                                                os.unlink(tempfilename)

                                                # set NODATA_VALUE metadata
                                                self.out_ds.SetMetadataItem('NODATA_VALUES','%s' % " ".join(str(int(f)) for f in self.in_nodata))
#                                               '%i %i %i' % (self.in_nodata[0],self.in_nodata[1],self.in_nodata[2]))

                                                if self.options.verbose:
                                                        print "Modified warping result saved into 'tiles1.vrt'"
                                                        open("tiles1.vrt","w").write(s)

                                        # -----------------------------------
                                        # Correction of AutoCreateWarpedVRT for Mono (1 band) and RGB (3 bands) files without NODATA:
                                        # equivalent of gdalwarp -dstalpha
                                        if self.in_nodata == [] and self.out_ds.RasterCount in [1,3]:
                                                import tempfile
                                                tempfilename = tempfile.mktemp('-gdal2tiles.vrt')
                                                self.out_ds.GetDriver().CreateCopy(tempfilename, self.out_ds)
                                                # open as a text file
                                                s = open(tempfilename).read()
                                                # Add the warping options
                                                s = s.replace("""<BlockXSize>""","""<VRTRasterBand dataType="Byte" band="%i" subClass="VRTWarpedRasterBand">
    <ColorInterp>Alpha</ColorInterp>
  </VRTRasterBand>
  <BlockXSize>""" % (self.out_ds.RasterCount + 1))
                                                s = s.replace("""</GDALWarpOptions>""", """<DstAlphaBand>%i</DstAlphaBand>
  </GDALWarpOptions>""" % (self.out_ds.RasterCount + 1))
                                                s = s.replace("""</WorkingDataType>""", """</WorkingDataType>
    <Option name="INIT_DEST">0</Option>""")
                                                # save the corrected VRT
                                                open(tempfilename,"w").write(s)
                                                # open by GDAL as self.out_ds
                                                self.out_ds = gdal.Open(tempfilename) #, gdal.GA_ReadOnly)
                                                # delete the temporary file
                                                os.unlink(tempfilename)

                                                if self.options.verbose:
                                                        print "Modified -dstalpha warping result saved into 'tiles1.vrt'"
                                                        open("tiles1.vrt","w").write(s)
                                        s = '''
                                        '''
                                                
                        else:
                                self.error("Input file has unknown SRS.", "Use --s_srs ESPG:xyz (or similar) to provide source reference system." )

                        if self.out_ds and self.options.verbose:
                                print "Projected file:", "tiles.vrt", "( %sP x %sL - %s bands)" % (self.out_ds.RasterXSize, self.out_ds.RasterYSize, self.out_ds.RasterCount)
                
                if not self.out_ds:
                        self.out_ds = self.in_ds

                #
                # Here we should have a raster (out_ds) in the correct Spatial Reference system
                #

                # KML test
                self.isepsg4326 = False
                srs4326 = osr.SpatialReference()
                srs4326.ImportFromEPSG(4326)
                if self.out_srs and srs4326.ExportToProj4() == self.out_srs.ExportToProj4():
                        self.kml = True
                        self.isepsg4326 = True
                        if self.options.verbose:
                                print "KML autotest OK!"

                # Instantiate image output.
                self.image_output = ImageOutput(self.options.tile_format, self.out_ds, self.tilesize,
                                                                                self.options.resampling, self.in_nodata, self.output)

                # Read the georeference 

                self.out_gt = self.out_ds.GetGeoTransform()
                        
                #originX, originY = self.out_gt[0], self.out_gt[3]
                #pixelSize = self.out_gt[1] # = self.out_gt[5]
                
                # Test the size of the pixel
                
                # MAPTILER - COMMENTED
                #if self.out_gt[1] != (-1 * self.out_gt[5]) and self.options.profile != 'raster':
                        # TODO: Process corectly coordinates with are have swichted Y axis (display in OpenLayers too)
                        #self.error("Size of the pixel in the output differ for X and Y axes.")
                        
                # Report error in case rotation/skew is in geotransform (possible only in 'raster' profile)
                if (self.out_gt[2], self.out_gt[4]) != (0,0):
                        self.error("Georeference of the raster contains rotation or skew. Such raster is not supported. Please use gdalwarp first.")
                        # TODO: Do the warping in this case automaticaly

                #
                # Here we expect: pixel is square, no rotation on the raster
                #

                # Output Bounds - coordinates in the output SRS
                self.ominx = self.out_gt[0]
                self.omaxx = self.out_gt[0]+self.out_ds.RasterXSize*self.out_gt[1]
                self.omaxy = self.out_gt[3]
                self.ominy = self.out_gt[3]-self.out_ds.RasterYSize*self.out_gt[1]
                # Note: maybe round(x, 14) to avoid the gdal_translate behaviour, when 0 becomes -1e-15

                if self.options.verbose:
                        print "Bounds (output srs):", round(self.ominx, 13), self.ominy, self.omaxx, self.omaxy

                #
                # Calculating ranges for tiles in different zoom levels
                #

                if self.options.profile == 'mercator':

                        self.mercator = GlobalMercator() # from globalmaptiles.py
                        
                        # Function which generates SWNE in LatLong for given tile
                        self.tileswne = self.mercator.TileLatLonBounds

                        # Generate table with min max tile coordinates for all zoomlevels
                        self.tminmax = range(0,32)
                        for tz in range(0, 32):
                                tminx, tminy = self.mercator.MetersToTile( self.ominx, self.ominy, tz )
                                tmaxx, tmaxy = self.mercator.MetersToTile( self.omaxx, self.omaxy, tz )
                                # crop tiles extending world limits (+-180,+-90)
                                tminx, tminy = max(0, tminx), max(0, tminy)
                                tmaxx, tmaxy = min(2**tz-1, tmaxx), min(2**tz-1, tmaxy)
                                self.tminmax[tz] = (tminx, tminy, tmaxx, tmaxy)

                        # TODO: Maps crossing 180E (Alaska?)

                        # Get the minimal zoom level (map covers area equivalent to one tile) 
                        if self.tminz == None:
                                self.tminz = self.mercator.ZoomForPixelSize( self.out_gt[1] * max( self.out_ds.RasterXSize, self.out_ds.RasterYSize) / float(self.tilesize) )

                        # Get the maximal zoom level (closest possible zoom level up on the resolution of raster)
                        if self.tmaxz == None:
                                self.tmaxz = self.mercator.ZoomForPixelSize( self.out_gt[1] )
                        
                        if self.options.verbose:
                                print "Bounds (latlong):", self.mercator.MetersToLatLon( self.ominx, self.ominy), self.mercator.MetersToLatLon( self.omaxx, self.omaxy)
                                print 'MinZoomLevel:', self.tminz
                                print "MaxZoomLevel:", self.tmaxz, "(", self.mercator.Resolution( self.tmaxz ),")"

                if self.options.profile == 'geodetic':

                        self.geodetic = GlobalGeodetic() # from globalmaptiles.py

                        # Function which generates SWNE in LatLong for given tile
                        self.tileswne = self.geodetic.TileLatLonBounds
                        
                        # Generate table with min max tile coordinates for all zoomlevels
                        self.tminmax = range(0,32)
                        for tz in range(0, 32):
                                tminx, tminy = self.geodetic.LatLonToTile( self.ominx, self.ominy, tz )
                                tmaxx, tmaxy = self.geodetic.LatLonToTile( self.omaxx, self.omaxy, tz )
                                # crop tiles extending world limits (+-180,+-90)
                                tminx, tminy = max(0, tminx), max(0, tminy)
                                tmaxx, tmaxy = min(2**(tz+1)-1, tmaxx), min(2**tz-1, tmaxy)
                                self.tminmax[tz] = (tminx, tminy, tmaxx, tmaxy)
                                
                        # TODO: Maps crossing 180E (Alaska?)

                        # Get the maximal zoom level (closest possible zoom level up on the resolution of raster)
                        if self.tminz == None:
                                self.tminz = self.geodetic.ZoomForPixelSize( self.out_gt[1] * max( self.out_ds.RasterXSize, self.out_ds.RasterYSize) / float(self.tilesize) )

                        # Get the maximal zoom level (closest possible zoom level up on the resolution of raster)
                        if self.tmaxz == None:
                                self.tmaxz = self.geodetic.ZoomForPixelSize( self.out_gt[1] )
                        
                        if self.options.verbose:
                                print "Bounds (latlong):", self.ominx, self.ominy, self.omaxx, self.omaxy
                                        
                if self.options.profile in ('raster', 'gearth'):
                        
                        log2 = lambda x: math.log10(x) / math.log10(2) # log2 (base 2 logarithm)
                        
                        self.nativezoom = int(max( math.ceil(log2(self.out_ds.RasterXSize/float(self.tilesize))),
                                                   math.ceil(log2(self.out_ds.RasterYSize/float(self.tilesize)))))
                        
                        if self.options.verbose:
                                print "Native zoom of the raster:", self.nativezoom

                        # Get the minimal zoom level (whole raster in one tile)
                        if self.tminz == None:
                                self.tminz = 0

                        # Get the maximal zoom level (native resolution of the raster)
                        if self.tmaxz == None:
                                self.tmaxz = self.nativezoom

                        # Generate table with min max tile coordinates for all zoomlevels
                        self.tminmax = range(0, self.tmaxz+1)
                        self.tsize = range(0, self.tmaxz+1)
                        for tz in range(0, self.tmaxz+1):
                                tsize = 2.0**(self.nativezoom-tz)*self.tilesize
                                tminx, tminy = 0, 0
                                tmaxx = int(math.ceil( self.out_ds.RasterXSize / tsize )) - 1
                                tmaxy = int(math.ceil( self.out_ds.RasterYSize / tsize )) - 1
                                self.tsize[tz] = math.ceil(tsize)
                                self.tminmax[tz] = (tminx, tminy, tmaxx, tmaxy)

                        self.tileswne = lambda x, y, z: (0,0,0,0)

        # -------------------------------------------------------------------------
        def generate_metadata(self):
                """Generation of main metadata files and HTML viewers (metadata related to particular tiles are generated during the tile processing)."""
                
                if not os.path.exists(self.output):
                        os.makedirs(self.output)

                if self.options.profile == 'mercator':
                        
                        south, west = self.mercator.MetersToLatLon( self.ominx, self.ominy)
                        north, east = self.mercator.MetersToLatLon( self.omaxx, self.omaxy)
                        south, west = max(-85.05112878, south), max(-180.0, west)
                        north, east = min(85.05112878, north), min(180.0, east)
                        self.swne = (south, west, north, east)

                        # Generate googlemaps.html
                        if self.options.webviewer in ('all','google') and self.options.profile == 'mercator':
                                if not self.options.resume or not os.path.exists(os.path.join(self.output, 'googlemaps.html')):
                                        f = open(os.path.join(self.output, 'googlemaps.html'), 'w')
                                        f.write( self.generate_googlemaps() )
                                        f.close()

                        # Generate openlayers.html
                        if self.options.webviewer in ('all','openlayers'):
                                if not self.options.resume or not os.path.exists(os.path.join(self.output, 'openlayers.html')):
                                        f = open(os.path.join(self.output, 'openlayers.html'), 'w')
                                        f.write( self.generate_openlayers() )
                                        f.close()

                elif self.options.profile == 'geodetic':
                        
                        west, south = self.ominx, self.ominy
                        east, north = self.omaxx, self.omaxy
                        south, west = max(-90.0, south), max(-180.0, west)
                        north, east = min(90.0, north), min(180.0, east)
                        self.swne = (south, west, north, east)
                        
                        # Generate openlayers.html
                        if self.options.webviewer in ('all','openlayers'):
                                if not self.options.resume or not os.path.exists(os.path.join(self.output, 'openlayers.html')):
                                        f = open(os.path.join(self.output, 'openlayers.html'), 'w')
                                        f.write( self.generate_openlayers() )
                                        f.close()                       

                elif self.options.profile == 'raster':
                        
                        west, south = self.ominx, self.ominy
                        east, north = self.omaxx, self.omaxy

                        self.swne = (south, west, north, east)
                        
                        # Generate openlayers.html
                        if self.options.webviewer in ('all','openlayers'):
                                if not self.options.resume or not os.path.exists(os.path.join(self.output, 'openlayers.html')):
                                        f = open(os.path.join(self.output, 'openlayers.html'), 'w')
                                        f.write( self.generate_openlayers() )
                                        f.close()                       


                # Generate tilemapresource.xml.
                if (self.options.tile_format != 'hybrid' and self.options.profile != 'gearth'
                        and (not self.options.resume or not os.path.exists(os.path.join(self.output, 'tilemapresource.xml')))):
                        f = open(os.path.join(self.output, 'tilemapresource.xml'), 'w')
                        f.write( self.generate_tilemapresource())
                        f.close()

        # -------------------------------------------------------------------------
        def generate_base_tiles(self):
                """Generation of the base tiles (the lowest in the pyramid) directly from the input raster"""
                
                print "Generating Base Tiles:"
                
                if self.options.verbose:
                        #mx, my = self.out_gt[0], self.out_gt[3] # OriginX, OriginY
                        #px, py = self.mercator.MetersToPixels( mx, my, self.tmaxz)
                        #print "Pixel coordinates:", px, py, (mx, my)
                        print
                        print "Tiles generated from the max zoom level:"
                        print "----------------------------------------"
                        print


                # Set the bounds
                tminx, tminy, tmaxx, tmaxy = self.tminmax[self.tmaxz]
                querysize = self.querysize

                # Just the center tile
                #tminx = tminx+ (tmaxx - tminx)/2
                #tminy = tminy+ (tmaxy - tminy)/2
                #tmaxx = tminx
                #tmaxy = tminy

                #print tminx, tminy, tmaxx, tmaxy
                tcount = (1+abs(tmaxx-tminx)) * (1+abs(tmaxy-tminy))
                #print tcount
                ti = 0
                
                ds = self.out_ds
                tz = self.tmaxz
                for ty in range(tmaxy, tminy-1, -1): #range(tminy, tmaxy+1):
                        for tx in range(tminx, tmaxx+1):

                                if self.stopped:
                                        break
                                ti += 1

                                #print "\tgdalwarp -ts 512 512 -te %s %s %s %s %s %s_%s_%s.tif" % ( b[0], b[1], b[2], b[3], "tiles.vrt", tz, tx, ty)

                                # Don't scale up by nearest neighbour, better change the querysize
                                # to the native resolution (and return smaller query tile) for scaling

                                if self.options.profile in ('mercator','geodetic'):
                                        if self.options.profile == 'mercator':
                                                # Tile bounds in EPSG:900913
                                                b = self.mercator.TileBounds(tx, ty, tz)
                                        elif self.options.profile == 'geodetic':
                                                b = self.geodetic.TileBounds(tx, ty, tz)

                                        rb, wb = self.geo_query( ds, b[0], b[3], b[2], b[1])
                                        nativesize = wb[0]+wb[2] # Pixel size in the raster covering query geo extent
                                        if self.options.verbose:
                                                print "\tNative Extent (querysize",nativesize,"): ", rb, wb

                                        querysize = self.querysize
                                        # Tile bounds in raster coordinates for ReadRaster query
                                        rb, wb = self.geo_query( ds, b[0], b[3], b[2], b[1], querysize=querysize)

                                        rx, ry, rxsize, rysize = rb
                                        wx, wy, wxsize, wysize = wb
                                else: # 'raster' or 'gearth' profile:
                                        
                                        tsize = int(self.tsize[tz]) # tilesize in raster coordinates for actual zoom
                                        xsize = self.out_ds.RasterXSize # size of the raster in pixels
                                        ysize = self.out_ds.RasterYSize
                                        if tz >= self.nativezoom:
                                                querysize = self.tilesize # int(2**(self.nativezoom-tz) * self.tilesize)

                                        rx = (tx) * tsize
                                        rxsize = 0
                                        if tx == tmaxx:
                                                rxsize = xsize % tsize
                                        if rxsize == 0:
                                                rxsize = tsize
                                        
                                        rysize = 0
                                        if ty == tmaxy:
                                                rysize = ysize % tsize
                                        if rysize == 0:
                                                rysize = tsize
                                        ry = ysize - (ty * tsize) - rysize

                                        wx, wy = 0, 0
                                        wxsize, wysize = int(rxsize/float(tsize) * self.tilesize), int(rysize/float(tsize) * self.tilesize)
                                        if wysize != self.tilesize:
                                                wy = self.tilesize - wysize

                                xyzzy = Xyzzy(querysize, rx, ry, rxsize, rysize, wx, wy, wxsize, wysize)

                                if self.options.resume:
                                        exists = self.image_output.tile_exists(tx, ty, tz)
                                        if exists and self.options.verbose:
                                                print "Tile generation skiped because of --resume"
                                else:
                                        exists = False

                                if not exists:
                                        try:
                                                if self.options.verbose:
                                                        print ti,'/',tcount
                                                        print "\tReadRaster Extent: ", (rx, ry, rxsize, rysize), (wx, wy, wxsize, wysize)

                                                self.image_output.write_base_tile(tx, ty, tz, xyzzy)
                                        except ImageOutputException, e:
                                                self.error("'%d/%d/%d': %s" % (tz, tx, ty, e.message))

                                if not self.options.verbose:
                                        self.progressbar( ti / float(tcount) )

        # -------------------------------------------------------------------------
        def generate_overview_tiles(self):
                """Generation of the overview tiles (higher in the pyramid) based on existing tiles"""
                
                print "Generating Overview Tiles:"
                
                # Usage of existing tiles: from 4 underlying tiles generate one as overview.
                
                tcount = 0
                for tz in range(self.tmaxz-1, self.tminz-1, -1):
                        tminx, tminy, tmaxx, tmaxy = self.tminmax[tz]
                        tcount += (1+abs(tmaxx-tminx)) * (1+abs(tmaxy-tminy))

                ti = 0
                
                # querysize = tilesize * 2

                for tz in range(self.tmaxz-1, self.tminz-1, -1):

                        tminx, tminy, tmaxx, tmaxy = self.tminmax[tz]
                        for ty in range(tmaxy, tminy-1, -1): #range(tminy, tmaxy+1):
                                for tx in range(tminx, tmaxx+1):
                                        
                                        if self.stopped:
                                                break
                                                
                                        ti += 1

                                        if self.options.resume:
                                                exists = self.image_output.tile_exists(tx, ty, tz)
                                                if exists and self.options.verbose:
                                                        print "Tile generation skiped because of --resume"
                                        else:
                                                exists = False

                                        if not exists:
                                                try:
                                                        if self.options.verbose:
                                                                print ti,'/',tcount
                                                                print "\tbuild from zoom", tz+1," tiles:", (2*tx, 2*ty), (2*tx+1, 2*ty),(2*tx, 2*ty+1), (2*tx+1, 2*ty+1)

                                                        self.image_output.write_overview_tile(tx, ty, tz)
                                                except Exception, e:
                                                        self.error("'%d/%d/%d': %s" % (tz, tx, ty, e.message))

                                        if not self.options.verbose:
                                                self.progressbar( ti / float(tcount) )

        # -------------------------------------------------------------------------
        def geo_query(self, ds, ulx, uly, lrx, lry, querysize = 0):
                """For given dataset and query in cartographic coordinates
                returns parameters for ReadRaster() in raster coordinates and
                x/y shifts (for border tiles). If the querysize is not given, the
                extent is returned in the native resolution of dataset ds."""

                geotran = ds.GetGeoTransform()
                rx= int((ulx - geotran[0]) / geotran[1] + 0.001)
                ry= int((uly - geotran[3]) / geotran[5] + 0.001)
                rxsize= int((lrx - ulx) / geotran[1] + 0.5)
                rysize= int((lry - uly) / geotran[5] + 0.5)

                if not querysize:
                        wxsize, wysize = rxsize, rysize
                else:
                        wxsize, wysize = querysize, querysize

                # Coordinates should not go out of the bounds of the raster
                wx = 0
                if rx < 0:
                        rxshift = abs(rx)
                        wx = int( wxsize * (float(rxshift) / rxsize) )
                        wxsize = wxsize - wx
                        rxsize = rxsize - int( rxsize * (float(rxshift) / rxsize) )
                        rx = 0
                if rx+rxsize > ds.RasterXSize:
                        wxsize = int( wxsize * (float(ds.RasterXSize - rx) / rxsize) )
                        rxsize = ds.RasterXSize - rx

                wy = 0
                if ry < 0:
                        ryshift = abs(ry)
                        wy = int( wysize * (float(ryshift) / rysize) )
                        wysize = wysize - wy
                        rysize = rysize - int( rysize * (float(ryshift) / rysize) )
                        ry = 0
                if ry+rysize > ds.RasterYSize:
                        wysize = int( wysize * (float(ds.RasterYSize - ry) / rysize) )
                        rysize = ds.RasterYSize - ry

                return (rx, ry, rxsize, rysize), (wx, wy, wxsize, wysize)

        # -------------------------------------------------------------------------

        # -------------------------------------------------------------------------
        def generate_tilemapresource(self):
                """
            Template for tilemapresource.xml. Returns filled string. Expected variables:
              title, north, south, east, west, isepsg4326, projection, publishurl,
              zoompixels, tilesize, tileformat, profile
                """

                args = {}
                args['title'] = self.options.title
                args['south'], args['west'], args['north'], args['east'] = self.swne
                args['tilesize'] = self.tilesize
                args['tileformat'] = format_extension[self.image_output.format]
                args['mime'] = format_mime[self.image_output.format]
                args['publishurl'] = self.options.url
                args['profile'] = self.options.profile
                
                if self.options.profile == 'mercator':
                        args['srs'] = "EPSG:900913"
                elif self.options.profile == 'geodetic':
                        args['srs'] = "EPSG:4326"
                elif self.options.s_srs:
                        args['srs'] = self.options.s_srs
                elif self.out_srs:
                        args['srs'] = self.out_srs.ExportToWkt()
                else:
                        args['srs'] = ""

                s = """<?xml version="1.0" encoding="utf-8"?>
        <TileMap version="1.0.0" tilemapservice="http://tms.osgeo.org/1.0.0">
          <Title>%(title)s</Title>
          <Abstract></Abstract>
          <SRS>%(srs)s</SRS>
          <BoundingBox minx="%(south).14f" miny="%(west).14f" maxx="%(north).14f" maxy="%(east).14f"/>
          <Origin x="%(south).14f" y="%(west).14f"/>
          <TileFormat width="%(tilesize)d" height="%(tilesize)d" mime-type="%(mime)s" extension="%(tileformat)s"/>
          <TileSets profile="%(profile)s">
""" % args
                for z in range(self.tminz, self.tmaxz+1):
                        if self.options.profile == 'raster':
                                s += """            <TileSet href="%s%d" units-per-pixel="%.14f" order="%d"/>\n""" % (args['publishurl'], z, (2**(self.nativezoom-z) * self.out_gt[1]), z)
                        elif self.options.profile == 'mercator':
                                s += """            <TileSet href="%s%d" units-per-pixel="%.14f" order="%d"/>\n""" % (args['publishurl'], z, 156543.0339/2**z, z)
                        elif self.options.profile == 'geodetic':
                                s += """            <TileSet href="%s%d" units-per-pixel="%.14f" order="%d"/>\n""" % (args['publishurl'], z, 0.703125/2**z, z)
                s += """          </TileSets>
        </TileMap>
        """
                return s
                        
        # -------------------------------------------------------------------------

# =============================================================================
# =============================================================================


def ImageOutput(name, out_ds, tile_size, resampling, nodata, output_dir):

        """Return object representing tile image output implementing given parameters."""

        resampler = Resampler(resampling)

        if name == "hybrid":
                return HybridImageOutput(out_ds, tile_size, resampler, nodata, output_dir)

        if name == "png":
                image_format = "PNG"
        elif name == "jpeg":
                image_format = "JPEG"

        return SimpleImageOutput(out_ds, tile_size, resampler, nodata, output_dir, [image_format])


class ImageOutputException(Exception):

        """Raised when the tile image can't be saved to disk."""


class BaseImageOutput(object):

        """Base class for image output.
        
        Child classes are supposed to provide two methods `write_base_tile' and
        `write_overview_tile'. These will call `create_base_tile' and `create_overview_tile'
        with arguments appropriate to their output strategy.

        When this class is instantiated with only one image format, it is stored in
        a member field `format'.
        """

        def __init__(self, out_ds, tile_size, resampler, nodata, output_dir, image_formats):
                self.out_ds = out_ds
                self.tile_size = tile_size
                self.resampler = resampler
                self.nodata = nodata
                self.output_dir = output_dir
                self.image_formats = image_formats
                if len(self.image_formats) == 1:
                        self.format = self.image_formats[0]

                self.mem_drv = get_gdal_driver("MEM")
                self.alpha_filler = None

                # For raster with 4-bands: 4th unknown band set to alpha
                if self.out_ds.RasterCount == 4 and self.out_ds.GetRasterBand(4).GetRasterColorInterpretation() == gdal.GCI_Undefined:
                        self.out_ds.GetRasterBand(4).SetRasterColorInterpretation(gdal.GCI_AlphaBand)

                # Get alpha band (either directly or from NODATA value)
                self.alpha_band = self.out_ds.GetRasterBand(1).GetMaskBand()
                if (self.alpha_band.GetMaskFlags() & gdal.GMF_ALPHA) or self.out_ds.RasterCount in (2, 4):
                        # TODO: Better test for alpha band in the dataset
                        self.data_bands_count = self.out_ds.RasterCount - 1
                else:
                        self.data_bands_count = self.out_ds.RasterCount

        def create_base_tile(self, tx, ty, tz, xyzzy, alpha, image_format):

                """Create image of a base level tile and write it to disk."""

                if alpha is None:
                        num_bands = self.data_bands_count
                else:
                        num_bands = self.data_bands_count + 1

                data_bands = range(1, self.data_bands_count+1)

                dstile = self.mem_drv.Create('', self.tile_size, self.tile_size, num_bands)
                data = self.out_ds.ReadRaster(xyzzy.rx, xyzzy.ry, xyzzy.rxsize, xyzzy.rysize,
                                                                          xyzzy.wxsize, xyzzy.wysize, band_list=data_bands)

                path = self.get_full_path(tx, ty, tz, format_extension[image_format])

                # Query is in 'nearest neighbour' but can be bigger in then the tilesize
                # We scale down the query to the tilesize by supplied algorithm.
                if self.tile_size == xyzzy.querysize:
                        # Use the ReadRaster result directly in tiles ('nearest neighbour' query)
                        dstile.WriteRaster(xyzzy.wx, xyzzy.wy, xyzzy.wxsize, xyzzy.wysize, data, band_list=data_bands)
                        if alpha is not None:
                                dstile.WriteRaster(xyzzy.wx, xyzzy.wy, xyzzy.wxsize, xyzzy.wysize, alpha, band_list=[num_bands])

                        gdal_write(path, dstile, image_format)

                        # Note: For source drivers based on WaveLet compression (JPEG2000, ECW, MrSID)
                        # the ReadRaster function returns high-quality raster (not ugly nearest neighbour)
                        # TODO: Use directly 'near' for WaveLet files
                else:
                        # Big ReadRaster query in memory scaled to the tilesize - all but 'near' algo
                        dsquery = self.mem_drv.Create('', xyzzy.querysize, xyzzy.querysize, num_bands)

                        # TODO: fill the null value in case a tile without alpha is produced (now only png tiles are supported)
                        if alpha is None:
                                for i,v in enumerate(self.nodata[:num_bands]):
                                        dsquery.GetRasterBand(i+1).Fill(v)

                        dsquery.WriteRaster(xyzzy.wx, xyzzy.wy, xyzzy.wxsize, xyzzy.wysize, data, band_list=data_bands)
                        if alpha is not None:
                                dsquery.WriteRaster(xyzzy.wx, xyzzy.wy, xyzzy.wxsize, xyzzy.wysize, alpha, band_list=[num_bands])

                        self.resampler(path, dsquery, dstile, image_format)

        def create_overview_tile(self, tx, ty, tz, image_format):

                """Create image of a overview level tile and write it to disk."""

                if image_format == "PNG":
                        num_bands = self.data_bands_count + 1
                else:
                        num_bands = self.data_bands_count

                dsquery = self.mem_drv.Create('', 2*self.tile_size, 2*self.tile_size, num_bands)

                if image_format == "PNG":
                        dsquery.GetRasterBand(num_bands).Fill(0)
                else:
                        for i,v in enumerate(self.nodata[:num_bands]):
                                dsquery.GetRasterBand(i+1).Fill(v)

                for cx, cy, child_image_format in self.iter_children(tx, ty, tz):
                        if (ty==0 and cy==1) or (ty!=0 and (cy % (2*ty)) != 0):
                                tileposy = 0
                        else:
                                tileposy = self.tile_size
                        if tx:
                                tileposx = cx % (2*tx) * self.tile_size
                        elif tx==0 and cx==1:
                                tileposx = self.tile_size
                        else:
                                tileposx = 0

                        path = self.get_full_path(cx, cy, tz+1, format_extension[child_image_format])
                        dsquerytile = gdal.Open(path, gdal.GA_ReadOnly)

                        dsquery.WriteRaster(tileposx, tileposy, self.tile_size, self.tile_size,
                                dsquerytile.ReadRaster(0, 0, self.tile_size, self.tile_size),
                                band_list=range(1, dsquerytile.RasterCount+1))

                        if image_format == "PNG" and dsquerytile.RasterCount != num_bands:
                                dsquery.WriteRaster(tileposx, tileposy, self.tile_size, self.tile_size,
                                        self.get_alpha_filler(), band_list=[num_bands])

                dstile = self.mem_drv.Create('', self.tile_size, self.tile_size, num_bands)
                path = self.get_full_path(tx, ty, tz, format_extension[image_format])
                self.resampler(path, dsquery, dstile, image_format)

        def iter_children(self, tx, ty, tz):
                """Generate all children of the given tile produced on the lower level."""
                for y in range(2*ty, 2*ty + 2):
                        for x in range(2*tx, 2*tx + 2):
                                image_format = self.try_to_use_existing_tile(x, y, tz+1)
                                if image_format is not None:
                                        yield x, y, image_format

        def read_alpha(self, xyzzy):
                return self.alpha_band.ReadRaster(xyzzy.rx, xyzzy.ry, xyzzy.rxsize, xyzzy.rysize, xyzzy.wxsize, xyzzy.wysize)

        def get_alpha_filler(self):
                if self.alpha_filler is None:
                        self.alpha_filler = "\xff" * (self.tile_size * self.tile_size)
                return self.alpha_filler

        def try_to_use_existing_tile(self, tx, ty, tz):
                """Return image format of the tile if it exists already on disk."""
                for image_format in self.image_formats:
                        if os.path.exists(self.get_full_path(tx, ty, tz, format_extension[image_format])):
                                return image_format
                return None

        def tile_exists(self, tx, ty, tz):
                return self.try_to_use_existing_tile(tx, ty, tz) != None

        def get_full_path(self, tx, ty, tz, extension):
                return os.path.join(self.output_dir, get_tile_filename(tx, ty, tz, extension))


class SimpleImageOutput(BaseImageOutput):

        """Image output using only one image format."""

        def write_base_tile(self, tx, ty, tz, xyzzy):
                if self.format == "PNG":
                        alpha = self.read_alpha(xyzzy)
                else:
                        alpha = None

                self.create_base_tile(tx, ty, tz, xyzzy, alpha, self.format)

        def write_overview_tile(self, tx, ty, tz):
                self.create_overview_tile(tx, ty, tz, self.format)


class HybridImageOutput(BaseImageOutput):

        """Image output which skips fully transparent tiles, saves the fully opaque
        as JPEG and the rest as PNG.
        
        Dummy files with extension `nil' are produced instead of the fully transparent
        tiles. Otherwise the resume feature wouldn't work.
        """

        def __init__(self, out_ds, tile_size, resampler, nodata, output_dir):
                BaseImageOutput.__init__(self, out_ds, tile_size, resampler, nodata, output_dir, ["JPEG", "PNG"])

        def write_base_tile(self, tx, ty, tz, xyzzy):
                alpha = self.read_alpha(xyzzy)
                transparent, opaque = self.transparent_or_opaque(alpha)

                if transparent:
                        return
                elif opaque:
                        image_format = "JPEG"
                        alpha = None
                else:
                        image_format = "PNG"

                self.create_base_tile(tx, ty, tz, xyzzy, alpha, image_format)

        def write_overview_tile(self, tx, ty, tz):
                children = list(self.iter_children(tx, ty, tz))

                if len(children) == 0:
                        return

                if any(image_format == "PNG" for x, y, image_format in children) or len(children) < 4:
                        image_format = "PNG"
                else:
                        image_format = "JPEG"

                self.create_overview_tile(tx, ty, tz, image_format)

        def transparent_or_opaque(self, alpha):
                transparent = opaque = True
                for c in alpha:
                        transparent = transparent and c == '\x00'
                        opaque = opaque and c == '\xff'
                assert not (transparent and opaque)
                return transparent, opaque


def Resampler(name):

        """Return a function performing given resampling algorithm."""

        def resample_average(path, dsquery, dstile, image_format):
                for i in range(1, dstile.RasterCount+1):
                        res = gdal.RegenerateOverview(dsquery.GetRasterBand(i), dstile.GetRasterBand(i), "average")
                        if res != 0:
                            raise ImageOutputException("RegenerateOverview() failed with error %d" % res)

                gdal_write(path, dstile, image_format)

        def resample_antialias(path, dsquery, dstile, image_format):
                querysize = dsquery.RasterXSize
                tilesize = dstile.RasterXSize

                array = numpy.zeros((querysize, querysize, 4), numpy.uint8)
                for i in range(dstile.RasterCount):
                        array[:,:,i] = gdalarray.BandReadAsArray(dsquery.GetRasterBand(i+1), 0, 0, querysize, querysize)
                im = Image.fromarray(array, 'RGBA') # Always four bands
                im1 = im.resize((tilesize,tilesize), Image.ANTIALIAS)

                if os.path.exists(path):
                        im0 = Image.open(path)
                        im1 = Image.composite(im1, im0, im1)

                ensure_dir_exists(path)
                im1.save(path, image_format)


        if name == "average":
                return resample_average
        elif name == "antialias":
                return resample_antialias

        resampling_methods = {
                "near"        : gdal.GRA_NearestNeighbour,
                "bilinear"    : gdal.GRA_Bilinear,
                "cubic"       : gdal.GRA_Cubic,
                "cubicspline" : gdal.GRA_CubicSpline,
                "lanczos"     : gdal.GRA_Lanczos
        }

        resampling_method = resampling_methods[name]

        def resample_gdal(path, dsquery, dstile, image_format):
                querysize = dsquery.RasterXSize
                tilesize = dstile.RasterXSize

                dsquery.SetGeoTransform( (0.0, tilesize / float(querysize), 0.0, 0.0, 0.0, tilesize / float(querysize)) )
                dstile.SetGeoTransform( (0.0, 1.0, 0.0, 0.0, 0.0, 1.0) )

                res = gdal.ReprojectImage(dsquery, dstile, None, None, resampling_method)
                if res != 0:
                    raise ImageOutputException("ReprojectImage() failed with error %d" % res)

                gdal_write(path, dstile, image_format)

        return resample_gdal


def gdal_write(path, dstile, image_format):
        ensure_dir_exists(path)
        driver = get_gdal_driver(image_format)
        driver.CreateCopy(path, dstile, strict=0)


def get_gdal_driver(name):
        driver = gdal.GetDriverByName(name)
        if driver is None:
                raise Exception("The '%s' driver was not found, is it available in this GDAL build?" % name)
        else:
                return driver


def get_tile_filename(tx, ty, tz, extension):
		gx, gy = GlobalMercator().GoogleTile(tx, ty, tz)
		return os.path.join(str(tz), str(gx), "%s.%s" % (gy, extension))


def ensure_dir_exists(path):
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
                os.makedirs(dirname)


class Xyzzy(object):

        """Collection of coordinates describing what to read where for the given tile at the base level."""

        def __init__(self, querysize, rx, ry, rxsize, rysize, wx, wy, wxsize, wysize):
                self.querysize = querysize
                self.rx = rx
                self.ry = ry
                self.rxsize = rxsize
                self.rysize = rysize
                self.wx = wx
                self.wy = wy
                self.wxsize = wxsize
                self.wysize = wysize


# =============================================================================


if __name__=='__main__':
        argv = gdal.GeneralCmdLineProcessor( sys.argv )
        if argv:
                gdal2tiles = GDAL2Tiles( argv[1:] )
                gdal2tiles.process()
