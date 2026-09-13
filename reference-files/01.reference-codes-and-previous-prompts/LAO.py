import os
import numpy as np
import pandas as pd
import datetime as dt
import logging
from pandas import ExcelWriter
from src.utilities.get_input_args import get_input_args
from src.utilities.functions import (
    my_function_today1, my_function_today2, LAO_Layout,
    my_function_newcomment, my_function_today3, my_function_print, save_dataframe_to_csv
)

# Set up the logger
logger = logging.getLogger("FMG_Automation")

def last_occurrence(output_df, user_initials):
    """
    Processes the input DataFrame to generate the Last Occurrence (LAO) report. 
    Includes data cleaning, transformations, and outputs a formatted CSV for LAO.
    Also generates an exception report as a supplemental feature if discrepancies are identified.

    Parameters:
    - output_df (DataFrame): Input data from prior steps.
    - user_initials (str): User initials for log tracking.

    Returns:
    - None: Outputs processed data to a CSV file and exceptions to an Excel file.
    """
    logger.info("Starting last_occurrence function.")

    try:
        # Set up date stamps
        Today, Today_2, Today_3 = my_function_today1(), my_function_today2(), my_function_today3()
        Today_4 = dt.datetime.now()
        logger.info(f"Date timestamps created: {Today}, {Today_2}, {Today_3}, {Today_4}")

        # Standardize column names
        output_df = output_df.rename(columns={"AnnualEstimate": "annual_estimate", "Counter reading": "Counter reading"})
        logger.info("Renamed columns for consistency.")

        # Prepare comment format with user initials
        Commentformat = my_function_newcomment(user_initials)
        logger.info(f"Updated comment format with user initials: {Commentformat}")

        # Prepare input arguments and exception report path
        in_arg = get_input_args()
        Nameformat_LAO = output_df.copy()
        exception_report_path = os.path.join(in_arg.except_dir, 'LAO_Exception_Report.xlsx')
        logger.info(f"Exception report will be saved to: {exception_report_path}")

        # Open an Excel writer for exceptions
        with pd.ExcelWriter(exception_report_path, engine='xlsxwriter') as exception_writer:

                # Step 1: Filter out 'Engine Midlife' except when equipment contains 'DT' and model is 793F
            engine_midlife_filter = Nameformat_LAO[Nameformat_LAO['Description'].str.contains("Engine Midlife", na=False)]

            # Identify rows to keep (equipment contains DT and model is 793F)
            condition_keep = (
                engine_midlife_filter['Equipment_y'].str.contains('DT', na=False) &
                (engine_midlife_filter['Model_y'] == '793F')
            )

            # Rows to exclude (Engine Midlife but does NOT meet keep condition)
            engine_midlife_exclude = engine_midlife_filter[~condition_keep]

            # Log and save excluded rows
            #save_dataframe_to_csv(engine_midlife_exclude, 'Engine_Midlife_filtered_out', suffix='')
            if not engine_midlife_exclude.empty:
                engine_midlife_exclude.to_excel(exception_writer, sheet_name='Engine_Midlife_Filtered', index=False)
                logger.info(f"Logged {len(engine_midlife_exclude)} 'Engine Midlife' records excluded.")

            # Remove only excluded rows from main DataFrame
            Nameformat_LAO = Nameformat_LAO.drop(engine_midlife_exclude.index)

            logger.info(f"Remaining DataFrame after filtering 'Engine Midlife' (kept rows meeting DT and 793F condition): {len(Nameformat_LAO)} rows remain.")




            #    # Step 2: Identify and remove duplicates in 'Functional Loc.' and log exceptions
            #     Nameformat_LAO['funcloc_desc'] = Nameformat_LAO['Functional Loc.'] + Nameformat_LAO['Description']
            #     duplicates = Nameformat_LAO[Nameformat_LAO.duplicated(subset=['funcloc_desc'], keep=False)]

            #     if not duplicates.empty:
            #         duplicates.to_excel(exception_writer, sheet_name='Duplicates', index=False)
            #         logger.info(f"Logged {len(duplicates)} duplicate records based on 'Functional Loc.' and 'Description'.")
            #     Nameformat_LAO.drop_duplicates(subset='funcloc_desc', keep='first', inplace=True)
            #     Nameformat_LAO.drop(columns=['funcloc_desc'], inplace=True)


#### -------------------------------------------- FINAL CLEAN UP FOR DATA PROCESSING ----------------------------------------------------------------------------------


            # Step 2: Identify and remove duplicates in 'Functional Loc.' and log exceptions
            Nameformat_LAO['funcloc_desc'] = Nameformat_LAO['Functional Loc.'] + Nameformat_LAO['Description']
            duplicates = Nameformat_LAO[Nameformat_LAO.duplicated(subset=['funcloc_desc'], keep=False)]
            #save_dataframe_to_csv(duplicates, 'LAO Duplicates',suffix='')
            if not duplicates.empty:
                duplicates.to_excel(exception_writer, sheet_name='Duplicates', index=False)
                logger.info(f"Logged {len(duplicates)} duplicate records based on 'Functional Loc.' and 'Description'.")


                # # Filter to keep rows where 'Functional Loc.' is similar and 'Description' contains 'C175'
                # Nameformat_LAO = Nameformat_LAO[~Nameformat_LAO.duplicated(subset=['Functional Loc.'], keep='first') | 
                #                                 (Nameformat_LAO['Description'].str.contains("C175", na=False))]

            # Drop rows where 'Meas/TotCtr' equals 'Counter reading'
            count_duplicates =  len(Nameformat_LAO[Nameformat_LAO['Meas/TotCtr'] == Nameformat_LAO['Counter reading']])
            print(f"The number of meas/tot with the same counter reading is: {count_duplicates}")
            # Identify duplicate Functional Loc. (excluding the first occurrence)
            duplicate_functional_locs = Nameformat_LAO.duplicated(subset=['Functional Loc.'], keep=False)

            # Apply filtering condition: Remove 'Meas/TotCtr == Counter reading' only for duplicate Functional Loc.
            filtered_LAO = Nameformat_LAO[~(duplicate_functional_locs & (Nameformat_LAO['Meas/TotCtr'] == Nameformat_LAO['Counter reading']))]

            # Ensure previous logic is retained: Remove duplicates (except first) OR keep "C175"
            Nameformat_LAO = filtered_LAO[~filtered_LAO.duplicated(subset=['Functional Loc.'], keep='first') | 
                                            (filtered_LAO['Description'].str.contains("C175", na=False))]

            logger.info("Filtered out 'Meas/TotCtr == Counter reading' only for duplicate Functional Loc. and applied existing filtering logic.")




            # Step 3: Populate mandatory fields
            Nameformat_LAO['BranchCode'] = Nameformat_LAO['Branch']
            Nameformat_LAO['SiteCode'] = Nameformat_LAO['Site']
            Nameformat_LAO['FleetCode'] = Nameformat_LAO['Fleet']
            Nameformat_LAO['CustomerCode'] = Nameformat_LAO['Customer']
            Nameformat_LAO['ModelCode'] = Nameformat_LAO['Model_y']
            logger.info(f"Populated Mandatory Field (Branch)")

            # Step 4: Format asset, serial, component, and task fields
            Nameformat_LAO['AssetName'] = Nameformat_LAO['Equipment_y']
            Nameformat_LAO['SerialNumber'] = Nameformat_LAO['Serial_Number_y']
            Nameformat_LAO['RegistrationCounter'] = '217040'
            Nameformat_LAO['ComponentCode'] = Nameformat_LAO['Component_Code_y'].str.split('-').str[0].str.strip()
            Nameformat_LAO['ModifierCode'] = Nameformat_LAO['Modifier_Code_y'].str.split('-').str[0].str.strip().apply(lambda x: f'="{x}"')
            Nameformat_LAO['TaskTypeCode'] = Nameformat_LAO['Task_Type'].str.split('-').str[0].str.strip()
            Nameformat_LAO['TaskCounterCode'] = Nameformat_LAO['Task_Counter'].astype(str)
            Nameformat_LAO['StrategyTaskDescription'] = Nameformat_LAO['ST_Description']
            Nameformat_LAO['FrequencyValue'] = Nameformat_LAO['Frequency']

            # Step 5: Additional Derived Fields for Analytics
            Nameformat_LAO['Is_changeout'] = (Nameformat_LAO['Meas/TotCtr'] - Nameformat_LAO['Counter reading']) > 0
            Nameformat_LAO['Recalibrate_smu'] = (Nameformat_LAO['Current_Usage'] - Nameformat_LAO['Meas/TotCtr']).abs() >= 700
            Nameformat_LAO['LAO_Concat'] = Nameformat_LAO['AssetName'] + Nameformat_LAO['ComponentCode'] + Nameformat_LAO['ModifierCode']
            logger.info("Derived fields for analytics added: Is_changeout, Recalibrate_smu, LAO_Concat.")

            # # Step 6: Data Reduction for AMT records > 1500
            # # Fill NaN values in 'Life_to_Date' with 'Current_reading'
            Nameformat_LAO['LifeToDateValue'] = Nameformat_LAO['Life_to_Date'].fillna(Nameformat_LAO['Counter reading'])
            # filtered_LAO = Nameformat_LAO[Nameformat_LAO['LifeToDateValue'] < 1500]
            # save_dataframe_to_csv(filtered_LAO, 'AMT LTD  MORE THAN 1500', suffix='')
            # if not filtered_LAO.empty:
            #     filtered_LAO.to_excel(exception_writer, sheet_name='AMT LTD  LESS THAN 1500', index=False)
            # Nameformat_LAO = Nameformat_LAO[Nameformat_LAO['LifeToDateValue'] > 1500]

            # Step 7:  Calculate the difference  and Filter customer records with usage difference +- 500
            Nameformat_LAO['Difference'] = (Nameformat_LAO['Counter reading'] - Nameformat_LAO['LifeToDateValue'])#.abs()
            # Identify records where Difference is between -500 and +500
            filtered_difference = Nameformat_LAO[Nameformat_LAO['Difference'].between(-500, 500)]
            # Save filtered records for review
            filtered_difference['Counter_Reading'] = Nameformat_LAO['Counter reading']
            save_dataframe_to_csv(filtered_difference, 'Cust LTD Between -500 and 500', suffix='')
                
            # Drop rows where Difference is between -500 and 500
            Nameformat_LAO.drop(Nameformat_LAO.index[Nameformat_LAO['Difference'].between(-500, 500)], inplace=True)
            logger.info("Filtered out records where Counter reading - LifeToDateValue is between -500 and 500.")

            # Step 8: Populate additional fields and assign SOS codes
            Nameformat_LAO['PrimaryPartNumberCode'] = Nameformat_LAO['Primary_Part_Number'].str.strip()
            Nameformat_LAO['NextPartNumberCode'] = Nameformat_LAO['Next_Part_Number'].fillna(Nameformat_LAO['Primary_Part_Number'])
            Nameformat_LAO['SourceOfSupplyCode'] = ''
            Nameformat_LAO.loc[~Nameformat_LAO['Primary_Part_Number'].str.contains('X|F', na=False), 'SourceOfSupplyCode'] = '000'
            Nameformat_LAO.loc[Nameformat_LAO['Primary_Part_Number'].str.endswith('F'), 'SourceOfSupplyCode'] = '483'
            Nameformat_LAO.loc[Nameformat_LAO['Primary_Part_Number'].str.find('X', 3) >= Nameformat_LAO['Primary_Part_Number'].str.len()-4, 'SourceOfSupplyCode'] = '503'

            # Step 9. Create and fill additional mandatory fields
            Nameformat_LAO['StrategyUOMCode'] = 'H'
            Nameformat_LAO['StrategyUsageValue'] = Nameformat_LAO['Strategy_Usage'] # Component end life
            Nameformat_LAO['LastStrategyUsageValue'] = Nameformat_LAO['Meas/TotCtr'].astype(int) - Nameformat_LAO['Counter reading'].astype(int) # to calculate the life remaining of a component vs machine
            logger.info("Filled usage and strategy fields")


            # Check of numbers of Strategy usage value vs Last Stregy Usage 
            higher_usage_count = (Nameformat_LAO['StrategyUsageValue'] > Nameformat_LAO['LastStrategyUsageValue']).sum()
            print(f"Number of StrategyUsageValue entries higher than Last StrategyUsageValue: {higher_usage_count}")

            higher_lastusage_count = (Nameformat_LAO['StrategyUsageValue'] < Nameformat_LAO['LastStrategyUsageValue']).sum()
            print(f"Number of StrategyUsageValue entries lesser than Last StrategyUsageValue: {higher_lastusage_count}")


            # Step 10: Finalize LAO output
            Nameformat_LAO['Date_1'] = pd.to_datetime(Nameformat_LAO['Strategy_Date'], errors='coerce')
            Nameformat_LAO.dropna(subset=['Date_1'], inplace=True)
            Nameformat_LAO['StrategyDate'] = Nameformat_LAO['Date_1'].dt.strftime('%Y%m%d')
            Nameformat_LAO.sort_values(by='StrategyDate', inplace=True)
            Nameformat_LAO.reset_index(drop=True, inplace=True)

            # Step 11 Additional mandatory fields
            Nameformat_LAO['NewStrategyDate'] = ''
            Nameformat_LAO['SalesStatusCode'] = Nameformat_LAO['Sales_Status']
            Nameformat_LAO['ReviewStatusCode'] = 'Not Reviewed'
            Nameformat_LAO['PartClassificationCode'] = ''
            Nameformat_LAO['SalesLostReasonCode'] = ''
            Nameformat_LAO.loc[Nameformat_LAO['SalesStatusCode'].str.contains('Lost', na=False), 'SalesLostReasonCode'] = 'Other'
            logger.info("Filled sales and review status fields")

            # Retain existing comment, concatenate system message    
            Nameformat_LAO['SalesStatusCommentsNote'] = Nameformat_LAO['Comments'] + " " + Commentformat
            Nameformat_LAO['SalesStatusCommentsNote'] = Nameformat_LAO['SalesStatusCommentsNote'].replace(np.nan, Commentformat, regex=True)
            logger.info("Updated sales status comments")

            # Create and fill mandatory fields
            Nameformat_LAO['PurchaseOrderNumber'] = Nameformat_LAO['PO_Number']

            # Create concat for testing and data reduction
            Nameformat_LAO['LAO_Concat'] = Nameformat_LAO['AssetName'] + Nameformat_LAO['ComponentCode'] + Nameformat_LAO['ModifierCode']

            # Order form by strategy date and reset index
            Nameformat_LAO = Nameformat_LAO.sort_values(by='StrategyDate')
            Nameformat_LAO.reset_index(inplace=True, drop=True)
            logger.info("Ordered data by strategy date and reset index")


            # Step 10: Save final LAO report as CSV
            Nameformat_LAO_Reduc = Nameformat_LAO[LAO_Layout()]
            Nameformat_LAO_Reduc.columns = LAO_Layout()
            my_function_print(Nameformat_LAO_Reduc, filepath=in_arg.output_dir, name='FMG', output_type='')

        logger.info("LAO output and exception report related to LAO saved successfully.")
        print('Complete - Saved to folder uploads')
    except Exception as e:
        logger.error(f"Error in last_occurrence function: {e}")
