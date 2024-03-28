#!/bin/bash

# Check if the ID argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <ID>"
    exit 1
fi

# Assign the ID argument to a variable
ID=$1

# Define the URL and directory names
URL="https://arcticdata.io/data/10.18739/A2KW57K57/iwp_geopackage_high/WGS1984Quad/15/$ID/"
DOWNLOAD_DIR="./"
OUTPUT_DIR="./arc_$ID"

# Download data using wget
wget -r -np -nH --cut-dirs=6 -R '\?C=' -R robots.txt "$URL" -P "$DOWNLOAD_DIR"

# Check if the download was successful
if [ $? -ne 0 ]; then
    echo "Error downloading data from $URL"
    exit 1
fi

# Convert downloaded data to ESRI Shapefile using ogr2ogr
mkdir -p "$OUTPUT_DIR"

# Iterate over each GeoPackage file in the current directory
for file in "$DOWNLOAD_DIR/$ID"/*.gpkg; do
    echo "converting..... $file"
    # Convert the GeoPackage file to ESRI Shapefile
    ogr2ogr -f "ESRI Shapefile" "$OUTPUT_DIR" "$file"
done

# Check if the conversion was successful
if [ $? -ne 0 ]; then
    echo "Error converting data to ESRI Shapefile"
    exit 1
fi

# Remove the downloaded directory
rm -rf "$DOWNLOAD_DIR/$ID"

echo "Data downloaded and converted successfully. Output directory: $OUTPUT_DIR"
