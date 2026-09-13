import os
import logging
import numpy as np
import pandas as pd
import xlsxwriter
from datetime import datetime as dt
from src.utilities.get_input_args import get_input_args
from src.utilities.functions import (
    my_function_today1,
    my_function_today2,
    NEO_Layout,
    my_function_newcomment,
    my_function_today3,
    my_function_print,
    save_dataframe_to_csv
)

# Set up the logger
logger = logging.getLogger("FMG_Automation")
logger.setLevel(logging.INFO)


def next_occurrence(output_df, user_initials):
    logger.info("Starting next_occurrence function")

    # Generate date timestamps
    Today = my_function_today1()
    Today_2 = my_function_today2()
    Today_3 = my_function_today3()
    Today_4 = pd.Timestamp.now()  # Use pandas for consistency
    
    logger.info(f"Generated date timestamps: Today={Today}, Today_2={Today_2}, Today_3={Today_3}, Today_4={Today_4}")

    # Rename columns for consistency
    logger.info("Renaming columns for consistency")
    output_df.rename(columns={"AnnualEstimate": "annual_estimate", "Counter reading": "counter_reading"}, inplace=True)

    # Add user initials to comments
    logger.info("Adding user initials to comments")
    Commentformat = my_function_newcomment(user_initials)

    # Get input arguments
    logger.info("Getting input arguments")
    in_arg = get_input_args()
    
    # Create a copy of the DataFrame
    logger.info("Creating a copy of the input DataFrame")
    Nameformat_NEO = output_df.copy()
    exception_report_path = os.path.join(in_arg.except_dir, 'NEO_Exception_Report.xlsx')
    

    # Use ExcelWriter for exception report
    with pd.ExcelWriter(exception_report_path, engine='xlsxwriter') as exception_writer:
        try:
            # Filter and save irrelevant 'Type' records
            # if 'Type' in Nameformat_NEO.columns:
            #     irrelevant_type_a_records = Nameformat_NEO[Nameformat_NEO['Type'].str.contains(" ", case=False)]
            #     save_dataframe_to_csv(irrelevant_type_a_records, 'Engine_Midlife_filter', suffix='')
            #     if not irrelevant_type_a_records.empty:
            #         irrelevant_type_a_records.to_excel(exception_writer, sheet_name='Irrelevant_Records_Type_A', index=False)
            #         logger.info(f"Logged {len(irrelevant_type_a_records)} irrelevant 'Type' records")
            #     Nameformat_NEO = Nameformat_NEO[~Nameformat_NEO['Type'].str.contains(" ", case=False)]

            # Filter and save irrelevant 'Type' records
            # if 'Type' in Nameformat_NEO.columns:
            #     irrelevant_type_a_records = Nameformat_NEO[Nameformat_NEO['Type'].str.contains(" ", case=False)]
            #     save_dataframe_to_csv(irrelevant_type_a_records, 'irrelevant_type_a_records', suffix='')
            #     if not irrelevant_type_a_records.empty:
            #         irrelevant_type_a_records.to_excel(exception_writer, sheet_name='Irrelevant_Records_Type', index=False)
            #         logger.info(f"Logged {len(irrelevant_type_a_records)} irrelevant 'Type' records")
                # Nameformat_NEO = Nameformat_NEO[~Nameformat_NEO['Type'].str.contains(" ", case=False)]

            # logger.info("Filtering out records where 'Task Name'")

            engine_midlife_records = Nameformat_NEO[Nameformat_NEO['Task Name'].str.contains("Engine Midlife complete", case=False)]
            save_dataframe_to_csv(engine_midlife_records, 'Engine_Midlife_complete', suffix='')
            if not engine_midlife_records.empty:
                engine_midlife_records.to_excel(exception_writer, sheet_name='Engine_Midlife_Complete', index=False)
                logger.info(f"Logged {len(engine_midlife_records)} 'Engine Midlife complete' records")
            Nameformat_NEO = Nameformat_NEO[~Nameformat_NEO['Task Name'].str.contains("Engine Midlife complete", case=False)]

            # Filter out the records where 'Task Name' contains "Engine Midlife complete"
            Nameformat_NEO = Nameformat_NEO[~Nameformat_NEO['Task Name'].str.contains("Engine Midlife complete", case=False)]

            # Fill mandatory fields
            mappings = {
                'BranchCode': 'Branch', 'SiteCode': 'Site', 'FleetCode': 'Fleet',
                'CustomerCode': 'Customer', 'ModelCode': 'Model_y', 'AssetName': 'Equipment_y',
                'SerialNumber': 'Serial_Number_y', 'RegistrationCounter': '217040'
            }
            for new_col, source_col in mappings.items():
                Nameformat_NEO[new_col] = Nameformat_NEO.get(source_col, '')

            # Drop rows where 'AssetName' is missing
            # logger.info("Dropping rows where 'AssetName' is missing")
            # Nameformat_NEO.dropna(subset=['AssetName'], inplace=True)
            initial_row_count = len(Nameformat_NEO)
            Nameformat_NEO.dropna(subset=['AssetName'], inplace=True)
            logger.info(f"Dropped rows with missing 'AssetName': {initial_row_count - len(Nameformat_NEO)} rows removed")

            # Populate part and task details
            logger.info("Populating ComponentCode, Modifier Code, TaskType, TaskCounter, StrategyTaskDescription,FrequencyValue,LifetoDateValue")
            Nameformat_NEO['ComponentCode'] = Nameformat_NEO['Component_Code_y'].str.split('-').str[0].str.strip()
            Nameformat_NEO['ModifierCode'] = Nameformat_NEO['Modifier_Code_y'].str.split('-').str[0].str.strip().apply('="{}"'.format)
            Nameformat_NEO['TaskTypeCode'] = Nameformat_NEO['Task_Type'].str.split('-').str[0].str.strip()
            Nameformat_NEO['TaskCounterCode'] = Nameformat_NEO['Task_Counter'].astype(str)
            Nameformat_NEO['StrategyTaskDescription'] = Nameformat_NEO['ST_Description']
            Nameformat_NEO['FrequencyValue'] = Nameformat_NEO['Frequency']
            Nameformat_NEO['LifeToDateValue'] = Nameformat_NEO['Life_to_Date'].fillna(0).astype(int)
            logger.info("Populated part and task details")

            # Handle primary and next part codes
            logger.info("Handling primary and next part codes")
            Nameformat_NEO['PrimaryPartNumberCode'] = Nameformat_NEO['Primary_Part_Number'].str.strip()
            Nameformat_NEO['NextPartNumberCode'] = Nameformat_NEO['Next_Part_Number'].fillna(Nameformat_NEO['Primary_Part_Number'])
            
            # Create Source of Supply (SOS) codes
            try:
                Nameformat_NEO['SourceOfSupplyCode_1'] = ''
                Nameformat_NEO.loc[~Nameformat_NEO['Primary_Part_Number'].str.contains('X', na=False), 'SourceOfSupplyCode_1'] = '000'
                Nameformat_NEO.loc[~Nameformat_NEO['Primary_Part_Number'].str.contains('F', na=False), 'SourceOfSupplyCode_1'] = '000'
                Nameformat_NEO.loc[Nameformat_NEO['Primary_Part_Number'].str.endswith('F'), 'SourceOfSupplyCode_1'] = '483'
                Nameformat_NEO.loc[Nameformat_NEO['Primary_Part_Number'].str.find('X', 3) >= Nameformat_NEO['Primary_Part_Number'].str.len() - 4, 'SourceOfSupplyCode_1'] = '503'
                Nameformat_NEO['SourceOfSupplyCode'] = Nameformat_NEO['SourceOfSupplyCode_1'].astype(str).apply('="{}"'.format)
            except Exception as e:
                logger.error(f"Error while creating Source of Supply codes: {e}")
                raise

            # More Mandatory Fields
            Nameformat_NEO['StrategyUOMCode'] = 'H'
            Nameformat_NEO['StrategyUsageValue'] = Nameformat_NEO['Strategy_Usage']
            Nameformat_NEO['NewStrategyUsageValue'] = ''
            
            

            # # Date transformations
            # logger.info("Performing date transformations")
            # Nameformat_NEO['Date_1'] = pd.to_datetime(Nameformat_NEO['Strategy_Date'], errors='coerce')
            # Nameformat_NEO['Start Date'] = pd.to_datetime(Nameformat_NEO['Due_Date'], errors='coerce')
            # Nameformat_NEO.dropna(subset=['Date_1', 'Start Date'], inplace=True)
            # logger.info("Calculated time deltas")

            # Nameformat_NEO['StrategyDate'] = Nameformat_NEO['Date_1'].dt.strftime('%Y%m%d')

            # Date transformations
            logger.info("Performing date transformations")
            Nameformat_NEO['Date_1'] = pd.to_datetime(Nameformat_NEO['Strategy_Date'], errors='coerce') # this lines converts the strategy dates to date format
            Nameformat_NEO['Start Date'] = pd.to_datetime(Nameformat_NEO['Due_Date'], errors='coerce') # Then if conversion fails it sets the value yo Nat(Not a Time) (Due Date derrives from LTP file Start)
            initial_row_count = len(Nameformat_NEO)
            Nameformat_NEO.dropna(subset=['Date_1', 'Start Date'], inplace=True) # Drops rows where either Date_1 or Start Date is NaT. Logs the number of rows removed. (Exception Report add it)
            logger.info(f"Dropped rows with missing or invalid dates: {initial_row_count - len(Nameformat_NEO)} rows removed")


            Nameformat_NEO['StrategyDate'] = Nameformat_NEO['Date_1'].dt.strftime('%Y%m%d') #Converts Date_1 and Start Date to string format YYYYMMDD.
            Nameformat_NEO['NewStrategyDate'] = Nameformat_NEO['Start Date'].dt.strftime('%Y%m%d') # Applying Start(LTP) as the New Strategy Date

            # Time delta calculations ( Calculates the number of days between Date_1 and Today_4, Start Date and Today_4, and Start Date and Date_1.)
            logger.info("Calculating time deltas") 
            Nameformat_NEO['t_delta_1'] = (Nameformat_NEO['Date_1'] - Today_4).dt.days # t delta 1 = Strategy Date (AMT) - NOW
            Nameformat_NEO['t_delta_2'] = (Nameformat_NEO['Start Date'] - Today_4).dt.days # t delta 2 = Start(LTP) - NOW
            Nameformat_NEO['t_delta_3'] = (Nameformat_NEO['Start Date'] - Nameformat_NEO['Date_1']).dt.days # Days between AMT and LTP


            # Business rule evaluation
            logger.info("Evaluating business rules time deltas")
            Nameformat_NEO['t_delta'] = Nameformat_NEO.apply(
                lambda row: not (
                    (row['t_delta_2'] <= row['t_delta_1'] < 0) or #(Date is in the past) Days between LTP Date and Now should not be less than or equal to AMT and less than 0 (Agreed to be deleted with FO and DP 10/1)
                    (row['t_delta_2'] < 0) or # Days between Start(LTP Date) and Today should not be less than 0
                    (row['t_delta_2'] > 730) or # Days between Start(LTP Date) and Today should not be greater than 730 - AMT should not have 2.5 year Gap [ this should be in exception report as
                    # anything that is more than 530 days means we have missed a changeout] --- Include these in the output but still produce exception report 18/2 DCA ----
                    (-30 <= row['t_delta_3'] <= 30) # days between AMT and LTP should not be  between -30 and 30 [ if its back a month and front a month should be checked]
                ),
                axis=1
            )

            # Create a 'Fail Reason' column with the reason why the row was excluded
            Nameformat_NEO['Fail Reason'] = Nameformat_NEO.apply(
                lambda row: (
                    'LTP Date is in the past' if row['t_delta_2'] < 0 else
                    'LTP Date is more than 2 years ahead' if row['t_delta_2'] > 730 else
                    'AMT and LTP Date are too close, LTP and AMT are ± 30 days' if -30 <= row['t_delta_3'] <= 30 else
                    None
                ),
                axis=1
            )

            initial_row_count = len(Nameformat_NEO)

            # Identify which data are being excluded base on business rules
            excluded_rows = Nameformat_NEO[~Nameformat_NEO['t_delta']]
            save_dataframe_to_csv(excluded_rows, in_arg.except_dir ,'Failed Business Rules')
            logger.info(f"Saved {len(excluded_rows)} excluded rows to 'Failed Business Rules'")

            # Business rules evaluation final
            # Final business rule: only keep records where both AMT (Date_1) and LTP (Start Date) are in the future or today

            logger.info("Evaluating business rules time deltas")
            Nameformat_NEO['business_rules'] = Nameformat_NEO.apply(
    # lambda row: (row['t_delta_1'] >= 0) and (row['t_delta_2'] >= 0),
    lambda row: (row['t_delta_2'] >= 0),
    axis=1
)
                
            # # Include only what applies with the business rules
            # Nameformat_NEO = Nameformat_NEO[Nameformat_NEO['business_rules']] # Deleted it as all NEO needs to be included 18/2/2025 DCA
            #logger.info(f"Dropped rows failing business rules: {initial_row_count - len(Nameformat_NEO)} rows needed to be check")
            Nameformat_NEO = Nameformat_NEO[Nameformat_NEO['business_rules']]

            # Save excluded past dates to exception report
            past_dates = Nameformat_NEO[Nameformat_NEO['Start Date'] < Today_4]
            if not past_dates.empty:
                save_dataframe_to_csv(past_dates, 'NEO_Past_Dates_Excluded', suffix='') # this is incase its not added in the exception report

                 # Ensure this is inside the ExcelWriter context for exception reporting
                past_dates.to_excel(exception_writer, sheet_name='Past_Dates_Excluded', index=False)
                logger.info(f"Excluded {len(past_dates)} records with Start Dates in the past.")

            else:
                logger.info("No past Start Dates found — skipping Past_Dates_Excluded sheet.")

            # Write to the exception report Excel file under a dedicated sheet
            # past_dates.to_excel(exception_writer, sheet_name='Past_Dates_Excluded', index=False)
            # logger.info(f"Logged and excluded {len(past_dates)} records with Start Dates in the past.")

            # Remove these rows from the main dataframe if there is any
            Nameformat_NEO = Nameformat_NEO[Nameformat_NEO['Start Date'] >= Today_4]
            

            # Unique key creation and filtering Removing any duplicates after calculations
            logger.info("Creating unique key and filtering duplicates")
            # Nameformat_NEO['NEO_Concat'] = Nameformat_NEO['AssetName'] + Nameformat_NEO['ComponentCode'] + Nameformat_NEO['ModifierCode']
            # Nameformat_NEO.drop_duplicates(subset=['NEO_Concat'], inplace=True) 

            # Step 1: Create unique group key (excluding dates)
            Nameformat_NEO['NEO_Concat'] = (
            Nameformat_NEO['AssetName'] +
            Nameformat_NEO['ComponentCode'] +
            Nameformat_NEO['ModifierCode'] 
            # Nameformat_NEO['StrategyDate'] +  # Include to differentiate on date
            # Nameformat_NEO['NewStrategyDate']
        )
            
            # Step 2: Convert NewStrategyDate to datetime for sorting
            Nameformat_NEO['NewStrategyDate'] = pd.to_datetime(Nameformat_NEO['NewStrategyDate'], format='%Y%m%d', errors='coerce')

            # Step 3: Sort by NewStrategyDate ascending to keep the earliest
            Nameformat_NEO.sort_values(by='NewStrategyDate', inplace=True)

            # Step 4: Drop duplicates keeping the first (earliest NewStrategyDate)
            Nameformat_NEO = Nameformat_NEO.drop_duplicates(subset=['NEO_Concat'], keep='first')

            # Optional: Drop helper column if no longer needed
            Nameformat_NEO.drop(columns=['NEO_Concat'], inplace=True)
            # Nameformat_NEO.drop_duplicates(subset=['NEO_Concat'], inplace=True)


            # Additional fields and comments
            logger.info("Adding more fields: Sales_Status, ReviewStatusCode, PartClassificationCode, SalesLostReasonCode, SalesStatusCommentNote")
            Nameformat_NEO['SalesStatusCode'] = Nameformat_NEO['Sales_Status']
            Nameformat_NEO['ReviewStatusCode'] = 'Not Reviewed'
            Nameformat_NEO['PartClassificationCode'] = Nameformat_NEO['Part_Classification']
            Nameformat_NEO['SalesLostReasonCode'] = Nameformat_NEO['Sales_Status'].apply(lambda x: 'Other' if 'Lost' in str(x) else '')
            Nameformat_NEO['SalesStatusCommentsNote'] = Commentformat + "; "+  Nameformat_NEO['Comments']
            Nameformat_NEO['PurchaseOrderNumber'] = Nameformat_NEO['PO_Number']

            # Final output columns
            logger.info("Selecting final output columns")
            layout_columns = NEO_Layout()
            Nameformat_NEO_Reduc = Nameformat_NEO[layout_columns]
            Nameformat_NEO_Reduc.columns = layout_columns

            logger.info("Next occurrence report completed and saved.")
            print('Completed - Saved to folder uploads')

        except Exception as e:
            logger.error(f"Error in next_occurrence function: {e}")
            raise

        # finally:
        #     logger.info("NEO report saved successfully.")
        #     return my_function_print(Nameformat_NEO_Reduc, filepath=in_arg.output_dir, name='FMG', output_type='NEO')


        # === Summary Sheet for Exception Report ===
        try:
            summary = pd.DataFrame({
                'Sheet Name': ['Past_Dates_Excluded', 'Irrelevant_Records_Type', 'Engine_Midlife_Complete', 'Failed Business Rules'],
                'Record Count': [
                    len(past_dates) if 'past_dates' in locals() else 0,
                    # len(irrelevant_type_a_records) if 'irrelevant_type_a_records' in locals() else 0,
                    len(engine_midlife_records) if 'engine_midlife_records' in locals() else 0,
                    len(excluded_rows) if 'excluded_rows' in locals() else 0
                ]
            })
            summary.to_excel(exception_writer, sheet_name='Summary', index=False)
            logger.info("Summary sheet added to the exception report.")
        except Exception as e:
            logger.warning(f"Failed to create summary sheet: {e}")


        finally:
            if 'Nameformat_NEO_Reduc' in locals():
                logger.info("NEO report saved successfully.")
                return my_function_print(Nameformat_NEO_Reduc, filepath=in_arg.output_dir, name='FMG', output_type='NEO')
            else:
                logger.warning("No output generated due to earlier failure.")
                return None

