# ArcPy Script to convert iwp shp files to sumerised table for aggregated counts 
# INPUT : iwp shape files duplicates marked <staging_du=1>, h3_tessellation_layer
# OUTPUT : Summery table with count for each Hexagonal cell in the h3_tessellation_layer
# TODO : All summery tables needs to be collected and aggregated (group_by) to get final counts
# TODO : Add the area also be aggregated if required at the same time
# Code is written to accumilate the counts for each run 
# i.e. if you do not give a new name for Summery table it will start updating the existing table
# When executing same shp file should not be processed twice

import arcpy
import os
import time

st_tme=time.time()
# Set the workspace and output directory
data_batch="arc_3776"
data_drive="C:"
data_directory="/iwp/"

#workspace = arcpy.env.workspace  # Use the current workspace
output_directory = os.path.join(data_drive,"/iwp/ag.gdb")  # Where to save the results
# An error was generated when the name of the file was longer due to a known issue 
# in ArcGIS when executing SummerizeWithin

print(output_directory)

if not os.path.exists(os.path.dirname(output_directory)):
    print("Parent directory does not exist:", os.path.dirname(output_directory))

# Create a new geodatabase if it doesn't exist
if not arcpy.Exists(output_directory):
    arcpy.CreateFileGDB_management(os.path.dirname(output_directory),os.path.basename(output_directory))

# Set the workspace to the output directory
arcpy.env.workspace = output_directory


# Read the h3 hexagonal tessalation shp file, Set the tessellation layer for summerized aggregations
#h3_tessellation_layer = os.path.join(data_drive,data_directory,"h3_hex","/arctic_h3hex_res5.shp")
h3_tessellation_layer = os.path.join(data_drive,data_directory,"h3_hex/arctic_h3hex_res5.shp")
#print(h3_tessellation_layer)

# Set the Directory containing polygon shapefiles to process
#shp_directory = "D:/IWP_ag/arc_test6/"
shp_directory = os.path.join(data_drive,data_directory,data_batch)  

# Set the name of summery table new name to be given if you want a new run
# Keeping the name short to avoid the name length error for summerize within
sum_table = "st1"

# Check if the summary table exists, if not, create it
if not arcpy.Exists(sum_table):
    print("New table created for Summary data")
    try:
        arcpy.CreateTable_management(output_directory, sum_table)
        arcpy.AddField_management(sum_table, "GRID_ID", "TEXT", field_length=50)
        arcpy.AddField_management(sum_table, "Sum_Cnt", "LONG")
    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))  # Print any error messages
else:
    print("Summary table already exists and will be used to add counts")

setup_tme=time.time()
print("Time to Setup=",setup_tme - st_tme)
######################################################
# Loop through each polygon shapefile in the directory
######################################################
#shp_directory = "D:/IWP_ag/arc_test5/"  # Directory containing polygon shapefiles
file_cnt=0
shp_files = [filename for filename in os.listdir(shp_directory) if filename.endswith('.shp')]
total_file_cnt=len(shp_files)
sumWithin=0 # status to check sumerized within executed successfully
for filename in shp_files:
    temp_sum = os.path.join(output_directory, "sw") #temp summary layer to keep the sumerize within
    #if filename.endswith(".shp"):
    polygon_shp = os.path.join(shp_directory, filename)
    desc = arcpy.Describe(polygon_shp)
    extent = desc.extent
    arcpy.env.extent = extent
    print("Extent set:", extent)
    try: # Execute SummarizeWithin for the layer 

        # Make new feature to count the polygons as arcGIS only allows SUM for aggregation
        # A new iwp cnt feature is added with "1" and later SUM ed
        # Also a check is done to see if the polygon is marked as a duplicate (not taken)
        st_tme=time.time()
        arcpy.management.MakeFeatureLayer(polygon_shp, "input_features_lyr", "staging_du <> 1")
        new_field_name = "iwp_cnt"
        existing_fields = [field.name for field in arcpy.ListFields("input_features_lyr")]
        if new_field_name not in existing_fields:
            # Add the new a field to the attribute table to be used for counting the polygons using SUM
            arcpy.AddField_management("input_features_lyr", new_field_name, "SHORT")

        # Calculate the new field with the value 1 for all rows
        arcpy.CalculateField_management("input_features_lyr", new_field_name, 1, "PYTHON3")
        print("Time to Create input Feature Layer = ",time.time() - st_tme)
        
        
        # Create a new point feature layer with centroids so the cells will not count same polygon more than once    
        st_tme=time.time()
        arcpy.FeatureToPoint_management("input_features_lyr", "centroid_points_lyr", "INSIDE")
        print("Time to Create point Feature Layer = ",time.time() - st_tme)
        
        arcpy.env.parallelProcessingFactor = "10"
        st_tme=time.time()
        arcpy.analysis.SummarizeWithin(h3_tessellation_layer, "centroid_points_lyr", temp_sum, "ONLY_INTERSECTING", [["iwp_cnt", "SUM"]])
        print("Time to Exec Sumerize Within = ",time.time() - st_tme)
        print(f"SummarizeWithin done for {filename}")

        # Print data collected from SummerizeWithin 
        # Just check and see if we have the fields required for the summary later
        # Can remove later
        result = arcpy.GetCount_management(temp_sum)
        polygon_count = int(result.getOutput(0))
        print("Number of H3 Cells in summary:", polygon_count)
        sumWithin=1
    except arcpy.ExecuteError:
        print(f"Failed to execute SummarizeWithin for {filename}:")
        sumWithin=0
        print(arcpy.GetMessages())

    # Update the summary table with the results from the current shapefile
    if (sumWithin==1):
        try:
            st_tme=time.time()
            # Reading the cummery data for the current layer
            with arcpy.da.SearchCursor(temp_sum, ["GRID_ID", "Sum_iwp_cnt"]) as cursor:
                print("Field names:", cursor.fields) 
                # Reading the summary data table to aggregate into
                with arcpy.da.UpdateCursor(sum_table, ["GRID_ID", "Sum_Cnt"]) as update_cursor:
                    print("Field names:", update_cursor.fields)  # Print field names
                    for row in cursor:
                        print(u'GRID_ID:{0}, iwp_cnt:{1},'.format(row[0], row[1]))
                        grid_id, sum_cnt = row
                        # Check if the H3_ID already exists in the summary table 
                        row_found = False
                        for update_row in update_cursor:
                            if update_row[0] == grid_id:
                                update_row[1] += sum_cnt
                                update_cursor.updateRow(update_row)
                                row_found = True
                                print("Updated:",grid_id, "with+:",sum_cnt)
                                break
                        if not row_found: # if not create new entry and add the row
                            with arcpy.da.InsertCursor(sum_table, ["GRID_ID", "Sum_Cnt"]) as insert_cursor:
                                insert_cursor.insertRow((grid_id, sum_cnt))              
            file_cnt+=1
            print("Time to Complete cell aggregation = ",time.time() - st_tme)
            print(f"Table Update Completed for {filename}, shp file {file_cnt} of {total_file_cnt}")
        except arcpy.ExecuteError:
            print(arcpy.GetMessages())

    #print(f"Table Update Completed for {filename,file_cnt,total_files})

    # Clean up temporary layers
if arcpy.Exists(temp_sum):
    arcpy.Delete_management(temp_sum)
    print("used temp summery deleted")
if arcpy.Exists("input_features_lyr"): # remove layer if already exisits
    arcpy.Delete_management("input_features_lyr")
    print("used input layer deleted")
if arcpy.Exists("centroid_points_lyr"): # remove layer if already exisits
    arcpy.Delete_management("centroid_points_lyr")
    print("used centroid point layer deleted")
    
# Write the output to a csv file
# File name auto generated based on the file batch

#csv_file = os.path.join(data_drive,data_directory,data_batch,".csv")
st_tme=time.time()
arcpy.env.overwriteOutput = True
csv_save_file = os.path.join(data_drive,data_directory,data_batch+"6.csv")
arcpy.management.CopyRows(sum_table, csv_save_file)
print("Time to Complete cell aggregation = ",time.time() - st_tme)    
print("===========================================================")
print("SummarizeWithin for all shapefiles completed. Output saved ")
print("Final Counts summary table.")
with arcpy.da.SearchCursor(sum_table, ["GRID_ID", "Sum_Cnt"]) as search_cursor:
    print("Field names:", search_cursor.fields)  # Print field names
    for row in search_cursor:
        print(u'GRID_ID:{0}, iwp_cnt:{1},'.format(row[0], row[1]))
print("==================DONE======================================")
