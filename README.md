# h3_hexagonal_iwp_sum
Aggregating the IWPs across the arctic
Scripts and pipeline to create H3 Hexagonal Aggregation summary for IWPs

H3 is a global grid indexing system and library developed by Uber to facilitate spatial data analysis. 
The H3 system uses a hierarchical hexagonal grid to tessellate the Earth's surface, allowing for efficient 
indexing and querying of spatial data at multiple levels of detail.

**Step 1**
Download the geopackage data from the Arctic Data Center(ADC). You can use the following script given as an example.
Make sure you have sufficient space 

```wget -r -np -nH --cut-dirs=3 -R '\?C=' -R robots.txt https://arcticdata.io/data/10.18739/A2KW57K57/iwp_geopackage_high/WGS1984Quad/15/3776```

**Step 2**
Convert the geopackage (.gpkg) file to ArcGIS readable shapefile (efficient) compared to reading from ArcGIS
```ogr2ogr -f "ESRI Shapefile" ./arc_3776 3776/*.gpkg```

**Step 3**
Run the [ArcPy Script](https://github.com/UConnARIAL/h3_hexagonal_iwp_sum/blob/main/h3_hexagonal_sum.py) for each (ex. 3776) batch of files

**Step 4**
Combine the summary table (csv files for each batch) via a database join on the h3 Hex grid ID.
