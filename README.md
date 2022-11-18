# Processing algorithms for SOTA summit analysis

Implementation in the scripts folder. This folder can be added to QGIS Processing search path and will be automatically inserted into the Processing toolbox when QGIS starts

## Import Landserf summits

1. add clipping border (optional) for example from GADM (gadm.org) select administrative division
(like a country) or multiple divisions and merge together; also insert a buffer around it of 0.001 degrees, so it will include summits right next to border
2. add virtual raster layer with the DEM data (can be created inside QGIS by selecting the
files which should be gdalbuildvrt-ed together)
3. run SOTA->Import Lanserf script
4. repeat for every virtual raster analysed by Landserf

## Merge summits together

1. run SOTA->Merge Summit Layers
2. select all vector layers created by the Import Landserf summits script (vector layer should be cleaned previously from
spurious and border summits)
3. choose neighborhood distance: the distance between summits that should be merged, DEM layers with 3 arcsecond resolution
can position summits within ±90m from each other, on flat summits this distance can increase due to random selection of
high point — an example distance for merging can be up to 500m or 0.005 degrees
4. distance measurement is controlled by output layer CRS definition (not working yet)
5. after merge, ridges (both summit and col) matching up will be collected into a multiline geometry
6. the resulting layer can and should be manually refined for cross-matching and summit/col mismatching errors

## Cleanup merged summits

After manually inspecting the merged summit list the following options can be added to the _Notes_
field:
- **x** exchange col with another entry (stored in the _Merge_ field), if summits were crossmatched
by Landserf, then this will select the correct col position
- **m** merge summit into another one (identified in either the _Merge_ field or the _Cross_ field)

## Calculate prominence for each DEM

This script will calculate the prominences of summits from input vector from the specified DEM
layers (by sampling the raster layer at the position of the summit and col) and store it in the output layer. This is just a reconing script.

## Calculate relative stats for a DEM

This script will calculate the input metrics for the statistic analysis about the DEM accuracy.
- input vector layer is a summits layer containing the summits and cols actual positions and elevations and the linestrings with the detected values
- a DEM raster layer has to be specified for the sampling input. The DEM layer must contain any of
SRTM, ASTER, ALOS, TDX or GLO30 in the name to identify the DEM linestring to be used from the input vector

The script will calculate the detected distance from the actual distance of summits/cols, and also return the actual elevations, the sampled elevation from the actual coordinates, the detected elevations and a best-guess crossmatch elevations. This values later on can be used to plot the
statistical results.
