import pandas as pd
import numpy as np
import os
import logging
from pandas import ExcelWriter
from src.utilities.get_input_args import get_input_args
from src.Scripts.taskname_filter import filter_values

# Set up the logger
logger = logging.getLogger("FMG_Automation")

def exception_report_lao(*exception_dfs):
    """
    Generates an exception report with tabs for:
    - NOT IN AMT
    - NOT IN CROSS REFERENCE
    - NOT IN LTP/IK17
    - DUPLICATES
    - MISSING VALUES
    - FILTER VALUES

    --Data Frames #
    1. exception_df_2, --> all the matches in between Xref IK17 and AMT
    2.IK17_ALLSITES, --> IK17 data
    3. All_AMT,  ---> AMT data
    4. Cross_IK17,  ---> merge between IK17 and Xref
    5. Cross_AMT, ---> merge between Xref and AMT



    Additionally, logs any Equipment not found in Functional Loc.

    Parameters:
    *exception_dfs: Variable number of DataFrames from different sources.

    Returns: 
    None: Writes the report to an Excel file.
    """
    logger.info("Starting exception report function")

    # Get input arguments and validate the output directory
    try:
        in_arg = get_input_args()
        if not os.path.exists(in_arg.except_dir):
            raise ValueError("Invalid or missing output directory. Please verify your input arguments.")
        logger.info("Input arguments retrieved and validated successfully")
    except Exception as e:
        logger.error(f"Error getting or validating input arguments: {e}")
        return


    try:
        output_file = os.path.join(in_arg.except_dir, 'LAO_Exception_Report.xlsx')
        with ExcelWriter(output_file, engine='xlsxwriter') as writer:
            summary_data = []  # Track exception counts

            # Process each DataFrame
            for idx, df in enumerate(exception_dfs, start=1):
                if df.empty:
                    logger.warning(f"DataFrame {idx} is empty and will be skipped.")
                    continue

                                # 1. IK17 NOT IN XREF
                if 'Merge_Cross_IK17' in df.columns:
                    ik17_not_xref = df[df['Merge_Cross_IK17'] == 'left_only']
                    if not ik17_not_xref.empty:
                        sheet_name = f'ik17_not_in_xref_{idx}'
                        ik17_not_xref.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(ik17_not_xref), "Exception Type": "IK17_NOT_IN_XREF"})
                        logger.info(f"Logged {len(ik17_not_xref)} records for IK17 NOT IN XREF in {sheet_name}")

                # 2. AMT ONLY NOT IN IK17
                if 'IK17_Cross_AMT' in df.columns:
                    amt_only_not_ik17 = df[df['IK17_Cross_AMT'] == 'right_only']
                    if not amt_only_not_ik17.empty:
                        amt_only_not_ik17['Note'] = 'Not in IK17'
                        sheet_name = f'amt_only_not_in_ik17_{idx}'
                        amt_only_not_ik17.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(amt_only_not_ik17), "Exception Type": "AMT_ONLY_NOT_IN_IK17"})
                        logger.info(f"Logged {len(amt_only_not_ik17)} records for AMT ONLY NOT IN IK17 in {sheet_name}")

                # 3. XREF ONLY NOT IN IK17
                if 'Merge_Cross_IK17' in df.columns:
                    xref_only_not_ik17 = df[df['Merge_Cross_IK17'] == 'right_only']
                    if not xref_only_not_ik17.empty:
                        xref_only_not_ik17['Comments_x'] = 'Not in Cross_reference'
                        sheet_name = f'xref_only_not_in_ik17_{idx}'
                        xref_only_not_ik17.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(xref_only_not_ik17), "Exception Type": "XREF_ONLY_NOT_IN_IK17"})
                        logger.info(f"Logged {len(xref_only_not_ik17)} records for XREF ONLY NOT IN IK17 in {sheet_name}")

                # 4. AMT ONLY NOT IN XREF
                if 'Xref_EquipAdmin' in df.columns:
                    amt_only_not_xref = df[df['Xref_EquipAdmin'] == 'right_only']
                    if not amt_only_not_xref.empty:
                        sheet_name = f'amt_only_not_in_xref_{idx}'
                        amt_only_not_xref.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(amt_only_not_xref), "Exception Type": "AMT_ONLY_NOT_IN_XREF"})
                        logger.info(f"Logged {len(amt_only_not_xref)} records for AMT ONLY NOT IN XREF in {sheet_name}")

                # 5. DUPLICATES
                if 'Functional Loc.' in df.columns:
                    duplicates = df[df.duplicated(subset=['Functional Loc.'], keep=False)]
                    if not duplicates.empty:
                        sheet_name = f'duplicates_{idx}'
                        duplicates.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(duplicates), "Exception Type": "DUPLICATES"})
                        logger.info(f"Logged {len(duplicates)} duplicate records in {sheet_name}")

                # 6. ENGINE MIDLIFE
                if 'Description' in df.columns:
                    engine_midlife = df[df['Description'].str.contains("Engine Midlife", na=False)]
                    if not engine_midlife.empty:
                        sheet_name = f'engine_midlife_{idx}'
                        engine_midlife.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(engine_midlife), "Exception Type": "ENGINE_MIDLIFE"})
                        logger.info(f"Logged {len(engine_midlife)} Engine Midlife records in {sheet_name}")

                # 7. FILTERED VALUES
                if 'Description' in df.columns:
                    try:
                        filter_list = filter_values()
                        filtered = df[df['Description'].str.contains('|'.join(filter_list), na=False)]
                        if not filtered.empty:
                            sheet_name = f'filtered_values_{idx}'
                            filtered.to_excel(writer, sheet_name=sheet_name, index=False)
                            summary_data.append({"Sheet": sheet_name, "Count": len(filtered), "Exception Type": "FILTERED_VALUES"})
                            logger.info(f"Logged {len(filtered)} filtered values in {sheet_name}")
                    except Exception as e:
                        logger.error(f"Error filtering values in DataFrame {idx}: {e}")

            # Write summary sheet
            if summary_data:
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='summary', index=False)
                logger.info("Summary sheet created successfully.")

        logger.info(f"Exception report saved at {output_file}")

    except Exception as e:
        logger.error(f"Error creating exception report: {e}")




# def exception_report_neo(*exception_dfs): 
#    # Get input arguments and validate the output directory
#     try:
#         in_arg = get_input_args()
#         if not os.path.exists(in_arg.except_dir):
#             raise ValueError("Invalid or missing output directory. Please verify your input arguments.")
#         logger.info("Input arguments retrieved and validated successfully")
#     except Exception as e:
#         logger.error(f"Error getting or validating input arguments: {e}")
#         return

#     # Create an output file for the exception report
#     try:
#         output_file = os.path.join(in_arg.except_dir, 'NEO_Exception_Report.xlsx')
#         with ExcelWriter(output_file, engine='xlsxwriter') as writer:
#             summary_data = []  # To track exception counts

#             # Process each DataFrame
#             for idx, df in enumerate(exception_dfs, start=1):
#                 if df.empty:
#                     logger.warning(f"DataFrame {idx} is empty and will be skipped.")
#                     continue

#                 # 1.LTP ONLY and Not In Xref 
#                 xref_only_not_amt = df[df['Xref_EquipAdmin'] == 'left_only']
#                 if not xref_only_not_amt.empty:
#                     sheet_name = f'xref_only_not_amt_{idx}'
#                     xref_only_not_amt.to_excel(writer, sheet_name=sheet_name, index=False)
#                     summary_data.append({"Sheet": sheet_name, "Count": len(xref_only_not_amt), "Exception Type": "LTP_NOT IN AMT"})
#                     logger.info(f"Logged {len(xref_only_not_amt)} records for LTP NOT IN AMT in sheet {sheet_name}")

#                 # 2. AMT only not in Xref
                
#                 AMT_ONLY_NOT_XREF = df[df['LTP_Cross_AMT'] == 'right_only']
#                 AMT_ONLY_NOT_XREF.loc[:, 'Note'] = 'Not in XREF'
#                 not_in_ltp = pd.concat([AMT_ONLY_NOT_XREF], ignore_index=True)

#                 if not not_in_ltp.empty:
#                     sheet_name = f'AMT_ONLY_NOT_LTP_{idx}'
#                     AMT_ONLY_NOT_XREF.to_excel(writer, sheet_name=sheet_name, index=False)
#                     summary_data.append({"Sheet": sheet_name, "Count": len(not_in_ltp), "Exception Type": "NOT IN LTP"})
#                     logger.info(f"Logged {len(not_in_ltp)} records for NOT IN LTP in sheet {sheet_name}")


#                 # 3. Xref ONLY and not in LTP
                
#                 XREF_ONLY_NOT_LTP = df[df['Merge_Cross_LTP'] == 'right_only']
#                 XREF_ONLY_NOT_LTP['Comments_x'] = 'Not in Cross_reference'
#                 not_in_xref = pd.concat([XREF_ONLY_NOT_LTP], ignore_index=True)

#                 if not not_in_xref.empty:
#                     sheet_name = f'XREF_ONLY_NOT_LTP_{idx}'
#                     XREF_ONLY_NOT_LTP.to_excel(writer, sheet_name=sheet_name, index=False)
#                     summary_data.append({"Sheet": sheet_name, "Count": len(not_in_xref), "Exception Type": "LTP ONLY not in XREF"})
#                     logger.info(f"Logged {len(not_in_xref)} records for NOT in Cross Reference in AMT ONLY {sheet_name}")

#                 # 4. Not in Cross Reference 

#                 # xref_only_not_amt = df[df['Xref_AMT_merge'] == 'left_only']
#                 # not_in_xref2 = pd.concat([xref_only_not_amt], ignore_index=True)

#                 # if not not_in_xref2.empty:
#                 #     sheet_name = f'AMT_ONLY_NOT_XREF_{idx}'
#                 #     xref_only_not_amt.to_excel(writer, sheet_name=sheet_name, index=False)
#                 #     summary_data.append({"Sheet": sheet_name, "Count": len(not_in_xref2), "Exception Type": "AMT ONLY not in XREF"})
#                 #     logger.info(f"Logged {len(not_in_xref2)} records for NOT in Cross reference and AMT ONLY {sheet_name}")

#                 try:
#                     amt_only_not_xref = df[df['LTP_Cross_AMT'] == 'right_only']
#                     not_in_xref2 = pd.concat([amt_only_not_xref], ignore_index=True)

#                     if not not_in_xref2.empty:
#                         idx = 1  # Ensure idx is defined
#                         sheet_name = f'AMT_ONLY_NOT_XREF_{idx}'
#                         amt_only_not_xref.to_excel(writer, sheet_name=sheet_name, index=False)
#                         summary_data.append({"Sheet": sheet_name, "Count": len(not_in_xref2), "Exception Type": "AMT ONLY not in XREF"})
#                         logger.info(f"Logged {len(not_in_xref2)} records for NOT in Cross reference and AMT ONLY {sheet_name}")

                    
#                     #ExcelWriter.close(output_file, engine='xlsxwriter')
#                 except Exception as e:
#                     logger.error(f"Error initializing Excel writer or saving the report: {e}")

          
#                 # # # 5. DUPLICATES - GETTING ERROR FROM IT
#                 # df['group_funcloc'] = df['group'] + df['Functional Loc.'] 
#                 # duplicates = df[df.duplicated(subset=['group_funcloc'], keep=False)]
#                 # if not duplicates.empty:
#                 #     sheet_name = f'DUPLICATES_{idx}'
#                 #     duplicates.to_excel(writer, sheet_name=sheet_name, index=False)
#                 #     summary_data.append({"Sheet": sheet_name, "Count": len(duplicates), "Exception Type": "duplicates"})
#                 #     logger.info(f"Logged {len(duplicates)} duplicate records in sheet {sheet_name}")

#                 engine_midlife_filter = df[df['Type'].str.contains("Engine Midlife complete", na=False)]
#                 if not engine_midlife_filter.empty:
#                     sheet_name = f'Engine Midlife_{idx}'
#                     engine_midlife_filter.to_excel(writer, sheet_name='Engine_Midlife_Filtered', index=False)
#                     logger.info(f"Logged {len(engine_midlife_filter)} 'Engine Midlife complete' records.")

#                 # # 6. Missing Values (Asset Names and Dates)
#                 # missing_values = df(df['Equipment'].isna())
#                 # if not missing_values.empty:
#                 #     missing_values['Comments_x'] = np.where(
#                 #         missing_values['Equipment'].isna(),
#                 #     )
#                 #     sheet_name = f'missing_values_{idx}'
#                 #     missing_values.to_excel(writer, sheet_name=sheet_name, index=False)
#                 #     summary_data.append({"Sheet": sheet_name, "Count": len(missing_values), "Exception Type": "Missing Values"})
#                 #     logger.info(f"Logged {len(missing_values)} records with missing values in sheet {sheet_name}")


#                 # 7. Filtered Values
#                 try:
#                     filter_list = filter_values()
#                     filtered_records = df[df['Task Name'].str.contains('|'.join(filter_list), na=False)]
#                     if not filtered_records.empty:
#                         sheet_name = f'NEO_FILTER_VALUES{idx}'
#                         filtered_records.to_excel(writer, sheet_name=sheet_name, index=False)
#                         summary_data.append({"Sheet": sheet_name, "Count": len(filtered_records), "Exception Type": "Filtered Values"})
#                         logger.info(f"Logged {len(filtered_records)} filtered records in sheet {sheet_name}")
#                 except Exception as e:
#                     logger.error(f"Error while filtering values in sheet {idx}: {e}")

#                 # Write summary sheet
#                 if summary_data:
#                     summary_df = pd.DataFrame(summary_data)
#                     summary_df.to_excel(writer, sheet_name='Summary', index=False)
#                     logger.info("Summary sheet created successfully")

                
#                 logger.info(f"Exception report saved successfully at {output_file}")

#     except Exception as e:
#         logger.error(f"Error initializing Excel writer or saving the report: {e}")



def exception_report_neo(*exception_dfs):
    """
    Generates NEO exception report with multiple tabs:
    - XREF ONLY NOT IN AMT
    - AMT ONLY NOT IN XREF
    - XREF ONLY NOT IN LTP
    - AMT ONLY NOT IN LTP
    - Engine Midlife
    - Filtered Values
    - Summary

    Parameters:
    *exception_dfs: Variable number of DataFrames to process.

    Returns:
    None: Saves the exception report as an Excel file.
    """
    logger.info("Starting NEO exception report function.")

    # Get input arguments and validate output directory
    try:
        in_arg = get_input_args()
        if not os.path.exists(in_arg.except_dir):
            raise ValueError("Invalid or missing output directory.")
        logger.info("Input arguments retrieved and validated successfully.")
    except Exception as e:
        logger.error(f"Error retrieving input arguments: {e}")
        return

    # Create exception report
    try:
        output_file = os.path.join(in_arg.except_dir, 'NEO_Exception_Report.xlsx')
        with ExcelWriter(output_file, engine='xlsxwriter') as writer:
            summary_data = []

            for idx, df in enumerate(exception_dfs, start=1):
                if df.empty:
                    logger.warning(f"DataFrame {idx} is empty. Skipping.")
                    continue

                # 1. XREF ONLY NOT IN AMT
                if 'Xref_EquipAdmin' in df.columns:
                    xref_only_not_amt = df[df['Xref_EquipAdmin'] == 'left_only']
                    if not xref_only_not_amt.empty:
                        sheet_name = f'Xref_ONLY_NOT_EquipAdmin_{idx}'
                        xref_only_not_amt.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(xref_only_not_amt), "Type": "XREF_ONLY_NOT_IN_AMT"})
                        logger.info(f"Logged {len(xref_only_not_amt)} XREF ONLY NOT IN AMT records.")

                # 1.A XREF ONLY NOT IN AMT
                if 'Xref_EquipAdmin' in df.columns:
                    xref_only_not_amt = df[df['Xref_EquipAdmin'] == 'right_only']
                    if not xref_only_not_amt.empty:
                        sheet_name = f'EquipAdmin_NOT_Xref_ONLY_{idx}'
                        xref_only_not_amt.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(xref_only_not_amt), "Type": "XREF_ONLY_NOT_IN_AMT"})
                        logger.info(f"Logged {len(xref_only_not_amt)} XREF ONLY NOT IN AMT records.")




                # 2. AMT ONLY NOT IN XREF
                if 'LTP_Cross_AMT' in df.columns:
                    amt_only_not_xref = df[df['LTP_Cross_AMT'] == 'right_only']
                    if not amt_only_not_xref.empty:
                        amt_only_not_xref['Note'] = 'Not in XREF'
                        sheet_name = f'AMT_ONLY_NOT_XREF_{idx}'
                        amt_only_not_xref.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(amt_only_not_xref), "Type": "AMT_ONLY_NOT_IN_XREF"})
                        logger.info(f"Logged {len(amt_only_not_xref)} AMT ONLY NOT IN XREF records.")

                # 3. XREF ONLY NOT IN LTP
                if 'Merge_Cross_LTP' in df.columns:
                    xref_only_not_ltp = df[df['Merge_Cross_LTP'] == 'right_only']
                    if not xref_only_not_ltp.empty:
                        xref_only_not_ltp['Comments_x'] = 'Not in Cross_reference'
                        sheet_name = f'XREF_ONLY_NOT_LTP_{idx}'
                        xref_only_not_ltp.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(xref_only_not_ltp), "Type": "XREF_ONLY_NOT_IN_LTP"})
                        logger.info(f"Logged {len(xref_only_not_ltp)} XREF ONLY NOT IN LTP records.")

                # 4. XREF ONLY NOT IN AMT
                if 'LTP_Cross_AMT' in df.columns:
                    amt_only_not_xref = df[df['LTP_Cross_AMT'] == 'left_only']
                    if not amt_only_not_xref.empty:
                        amt_only_not_xref['Note'] = 'Not in LTP'
                        sheet_name = f'LTP_ONLY_NOT_AMT_{idx}'
                        amt_only_not_xref.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(amt_only_not_xref), "Type": "Xref_Only_Not_LTP"})
                        logger.info(f"Logged {len(amt_only_not_xref)} AMT ONLY NOT IN LTP records.")

                # 5. Engine Midlife
                if 'Type' in df.columns:
                    engine_midlife = df[df['Type'].str.contains("Engine Midlife complete", na=False)]
                    if not engine_midlife.empty:
                        sheet_name = f'ENGINE_MIDLIFE_{idx}'
                        engine_midlife.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(engine_midlife), "Type": "ENGINE_MIDLIFE"})
                        logger.info(f"Logged {len(engine_midlife)} Engine Midlife records.")


                # Add this inside the loop where idx and df are defined
                if 'Start Date' in df.columns and 'Date_1' in df.columns:
                    today = pd.Timestamp.today().normalize()
                    if df[['Start Date', 'Date_1']].lt(today).any(axis=1).all():
                        sheet_name = f'PAST_DATES_{idx}'
                        df['Note'] = 'Excluded due to past Start Date or Strategy Date'
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        summary_data.append({"Sheet": sheet_name, "Count": len(df), "Type": "PAST_DATES"})
                        logger.info(f"Logged {len(df)} past date records in sheet {sheet_name}")
                        continue


                # # 6. Filtered Values
                # try:
                #     filter_list = filter_values()
                #     filtered_records = df[df['Task Name'].str.contains('|'.join(filter_list), na=False)]
                #     if not filtered_records.empty:
                #         sheet_name = f'FILTERED_VALUES_{idx}'
                #         filtered_records.to_excel(writer, sheet_name=sheet_name, index=False)
                #         summary_data.append({"Sheet": sheet_name, "Count": len(filtered_records), "Type": "FILTERED_VALUES"})
                #         logger.info(f"Logged {len(filtered_records)} filtered records.")
                # except Exception as e:
                #     logger.error(f"Error filtering values for DataFrame {idx}: {e}")

            # Write summary tab at the end
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='SUMMARY', index=False)
                logger.info("Summary sheet created.")

        logger.info(f"NEO exception report saved successfully at {output_file}")

    except Exception as e:
        logger.error(f"Error creating NEO exception report: {e}")
