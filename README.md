# Processing algorithms for SOTA summit analysis

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
high point — an example distance for merging can be up to 500m or 0.0005 degrees
4. distance measurement is controlled by output layer CRS definition (not working yet)
5. after merge, ridges (both summit and col) matching up will be collected into a multiline geometry
6. the resulting layer can and should be manually refined for cross-matching and summit/col mismatching errors