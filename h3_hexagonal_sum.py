# ArcPy Script to convert iwp shp files to sumerised table for aggregated counts 
# INPUT : iwp shape files duplicates marked <staging_du=1>, h3_tessellation_layer
# OUTPUT : Summery table with count for each Hexagonal cell in the h3_tessellation_layer
#
# Code is written to accumilate the counts for each run 
# i.e. if you do not give a new name for Summery table it will start updating the existing table
# When executing same shp file should not be processed twice

import arcpy
import os
import time
import sys

# Set the workspace and output directory
data_batch="arc_3775"
data_drive="D:"
data_directory="/iwp_ag3/"
h3_hex_file_name = "h3_hex/arctic_h3hex_res5.shp"

output_directory = os.path.join(data_drive,"/ag.gdb")  # Where to save the results

def find_h3_cell(extent,h3_tessellation_layer,output_location):
    """
    Function to use select by location to reduce the more expensive calls for sumerizewithin
    Logic, if the extent of the IWP input cell falls inside totaly it will be counted and 
    added to the h3 cell eithout a call to summerie within.
    Will return the selected number of H3 Cells OR if count is ==1 will return the h3 Cell ID
    
    """
    st_tme=time.time()
    temp_fc_name = "FeatureClass"
    # Create the feature class
    temp_fc = arcpy.management.CreateFeatureclass(output_location, temp_fc_name, "POLYGON")[0]
    # Create a temporary feature layer from the feature class
    temp_layer = arcpy.management.MakeFeatureLayer(temp_fc, "temp_layer1")[0]
    # Start an edit session
    edit = arcpy.da.Editor(output_location)
    edit.startEditing(False, True)
    edit.startOperation()
    # Insert a new feature into the temporary feature class
    with arcpy.da.InsertCursor(temp_fc, ["SHAPE@"]) as cursor:
        cursor.insertRow([arcpy.Polygon(arcpy.Array([arcpy.Point(extent.XMin, extent.YMin),
                                                      arcpy.Point(extent.XMin, extent.YMax),
                                                      arcpy.Point(extent.XMax, extent.YMax),
                                                      arcpy.Point(extent.XMax, extent.YMin)]))])
    # Stop the edit operation and save changes
    edit.stopOperation()
    edit.stopEditing(True)
    # Create a temporary feature layer from the feature class
    temp_layer = arcpy.management.MakeFeatureLayer(temp_fc, "temp_layer")[0]
    print("Time to Create Temp Layer = ",time.time() - st_tme)
    fc = os.path.join(output_location,"fc1")
    selection_type = "INTERSECT" 
    st_tme=time.time()
    selected_hex=arcpy.SelectLayerByLocation_management(in_layer=h3_tessellation_layer,
                                           overlap_type=selection_type,
                                           select_features=temp_layer)
    arcpy.CopyFeatures_management(selected_hex,fc)
    result = arcpy.GetCount_management(h3_tessellation_layer)
    selected_count = int(result.getOutput(0))
    print("Number of selected features:",selected_count)  
    
    """"
    if arcpy.Exists(h3_tessellation_layer):
        arcpy.Delete_management(h3_tessellation_layer)
        print("used h3_tessellation_layer deleted")
    """
    print("Time to Exec Layer by Location = ",time.time() - st_tme)    
    selected_grid="None"
    if (selected_count==1):
        with arcpy.da.SearchCursor(fc, ["GRID_ID"]) as cursor:
            for row in cursor:
                print(u'Only One Selected GRID_ID:{0},'.format(row[0]))
                selected_grid=row[0]
    return(selected_count,selected_grid)

def create_in_layer_drop_duplicates(input_shp_file,input_fl="input_features_lyr"):
    # Make new feature to count the polygons as arcGIS only allows SUM for aggregation
    # A new iwp cnt feature is added with "1" and later SUM ed
    # Also a check is done to see if the polygon is marked as a duplicate (not taken)
    st_tme=time.time()
    arcpy.management.MakeFeatureLayer(polygon_shp, input_fl, "staging_du <> 1")
    new_field_name = "iwp_cnt"
    existing_fields = [field.name for field in arcpy.ListFields("input_features_lyr")]
    if new_field_name not in existing_fields:
        # Add the new a field to the attribute table to be used for counting the polygons using SUM
        arcpy.AddField_management("input_features_lyr", new_field_name, "SHORT")

    # Calculate the new field with the value 1 for all rows
    arcpy.CalculateField_management("input_features_lyr", new_field_name, 1, "PYTHON3")
    print("Time to Create input Feature Layer = ",time.time() - st_tme)


if __name__ == "__main__":
    st_tme=time.time()   
    
    if not os.path.exists(os.path.dirname(output_directory)):
        print("Parent directory does not exist:", output_directory)
        sys.exit(1)
        
    # Create a new geodatabase if it doesn't exist
    if not arcpy.Exists(output_directory):
        arcpy.CreateFileGDB_management(os.path.dirname(output_directory),os.path.basename(output_directory))

    # Set the workspace to the output directory
    arcpy.env.workspace = output_directory

    # Read the h3 hexagonal tessalation shp file, Set the tessellation layer for summerized aggregations
    h3_tessellation_layer = os.path.join(data_drive,data_directory,h3_hex_file_name)
    # Get the Directory containing polygon shapefiles to process
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
    file_cnt=0
    shp_files = [filename for filename in os.listdir(shp_directory) if filename.endswith('.shp')]
    total_file_cnt=len(shp_files)
    sumWithin=0 # status to check sumerized within executed successfully
    cell_iwp_cnt=0 # Temp variable to store the total number of iwps in a cell when selected by location
    for filename in shp_files:
        temp_sum = os.path.join(output_directory, "sw") #temp summary layer to keep the sumerize within
        polygon_shp = os.path.join(shp_directory, filename)
        desc = arcpy.Describe(polygon_shp)
        extent = desc.extent
        arcpy.env.extent = extent
        print("Extent set:", extent)
        try:
            create_in_layer_drop_duplicates(polygon_shp,"input_features_lyr")
                
            # Find out if the input shp file extent falls inside a h3 cell
            # If yes we can take all points without the sumerize within
            selected_h3s, selected_h3_id=find_h3_cell(extent,h3_tessellation_layer,output_directory)
            print("Selected H3:",selected_h3s)
            if (selected_h3s>1): #if the input shp file DOES NOT fall inside an h3 cell
                # Create a new point feature layer with centroids so the cells will not count same polygon more than once    
                st_tme=time.time()
                arcpy.FeatureToPoint_management("input_features_lyr", "centroid_points_lyr", "INSIDE")
                print("Time to Create point Feature Layer = ",time.time() - st_tme)
                st_tme=time.time()
                arcpy.analysis.SummarizeWithin(h3_tessellation_layer, "centroid_points_lyr", temp_sum, "ONLY_INTERSECTING", [["iwp_cnt", "SUM"]])
                print("Time to Exec Sumerize Within = ",time.time() - st_tme)

                result = arcpy.GetCount_management(temp_sum)
                polygon_count = int(result.getOutput(0))
                print("Number of H3 Cells in summary:", polygon_count)
                sumWithin=1
            elif(selected_h3s==1):
                cell_iwp_cnt=int((arcpy.GetCount_management("input_features_lyr")).getOutput(0))
                print("IWPs in Cell",cell_iwp_cnt)
                  
        except arcpy.ExecuteError:
            print(f"Failed to execute SummarizeWithin for {filename}:")
            sumWithin=0
            print(arcpy.GetMessages())
        # Update the summary table with the results from the current shapefile
        if (sumWithin==1):
            try:
                st_tme=time.time()     
                # Reading the summary data for the current layer
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
                print("Time to Complete cell aggregation = ",time.time() - st_tme)
                #print(f"Table Update Completed for {filename}, shp file {file_cnt} of {total_file_cnt}")
            except arcpy.ExecuteError:
                print(arcpy.GetMessages())
        elif (selected_h3s==1):
              with arcpy.da.UpdateCursor(sum_table, ["GRID_ID", "Sum_Cnt"]) as update_cursor:
                    print("Field names:", update_cursor.fields)  # Print field names
                    grid_id=selected_h3_id
                    sum_cnt = cell_iwp_cnt
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
        #print(f"Table Update Completed for {filename,file_cnt,total_files})
        file_cnt+=1
        print(f"Table Update Completed for {filename}, shp file {file_cnt} of {total_file_cnt}")
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
    csv_save_file = os.path.join(data_drive,data_directory,data_batch+"7.csv")
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
