import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import Border, Side, Font
from openpyxl.utils import get_column_letter
import re
import logging
from src.utilities.get_input_args import get_input_args

# Set up logger
logger = logging.getLogger(__name__)

def discrepancy_report(output_df):
    """
    Generates a discrepancy report by identifying rows with missing or inconsistent data in the output DataFrame.
    The report is saved to an Excel file with formatted headers and columns.
    """
    logger.info("Starting discrepancy_report function")

    # Get input arguments
    try:
        in_arg = get_input_args()
        logger.info("Input arguments retrieved successfully")
    except Exception as e:
        logger.error(f"Error getting input arguments: {e}")
        return

    try:
        # Prepare the discrepancy DataFrame
        discrepancy_df = output_df.copy()
        discrepancy_df['Component_Code_Description_Concat'] = (
            discrepancy_df['Component_Code'].astype(str) + 
            discrepancy_df['Component_Code_Description'].astype(str)
        )
        discrepancy_df['Concat'] = (
            discrepancy_df['Equipment'].astype(str) + 
            discrepancy_df['Component_Code_Description_Concat'] + 
            discrepancy_df['Modifier_Code'].astype(str)
        )

        # Drop duplicates
        initial_count = len(discrepancy_df)
        discrepancy_df.drop_duplicates(subset=['Concat'], keep='first', inplace=True)
        duplicates_removed = initial_count - len(discrepancy_df)
        logger.info(f"Removed {duplicates_removed} duplicate rows based on 'Concat'")

        # Convert dates and calculate date ranges
        discrepancy_df['Start Date'] = pd.to_datetime(discrepancy_df['Start'], errors='coerce') # 18/11 HWA: no "Start" column in IK17 df
        discrepancy_df['New_Strategy_Date'] = discrepancy_df['Start Date'].dt.to_period('M').dt.to_timestamp()
        discrepancy_df['Strategy_Date'] = pd.to_datetime(discrepancy_df['Strategy_Date'], errors='coerce').dt.to_period('M').dt.to_timestamp()

        min_date = min(discrepancy_df['New_Strategy_Date'].min(), discrepancy_df['Strategy_Date'].min())
        max_date = max(discrepancy_df['New_Strategy_Date'].max(), discrepancy_df['Strategy_Date'].max())
        logger.info(f"Date range calculated: {min_date} to {max_date}")

        # Prepare the date range DataFrame for pivot tables
        date_range_df = pd.DataFrame({'Date': pd.date_range(start=min_date, end=max_date, freq='M')})
        date_range_df['Date'] = date_range_df['Date'].dt.strftime('%d/%m/%Y')
        date_range_df['Count'] = 0
        date_range_subset = date_range_df.pivot_table(columns='Date', values='Count', aggfunc='sum')

        # Create WesTrac/Customer comparison pivots
        discrepancy_df['ID'] = (
            discrepancy_df['Branch'] + discrepancy_df['Site'] + 
            discrepancy_df['Model'] + discrepancy_df['Component_Code_Description_Concat']
        )
        Pivot_wesTrac = discrepancy_df.pivot_table(index='ID', columns='Strategy_Date', values='Count', aggfunc='sum').reset_index()
        Pivot_customer = discrepancy_df.pivot_table(index='ID', columns='New_Strategy_Date', values='Count', aggfunc='sum').reset_index()

        # Merge and align data
        merged_table = date_range_subset.merge(Pivot_wesTrac, how='right')
        merged_table = merged_table.sort_index(axis=1)
        final_table = merged_table.T.reset_index().T.reset_index(drop=True)

        # Create final output file
        print_time = pd.to_datetime("today").strftime('%d%m%Y')
        output_file = f"{in_arg.analysis_dir}FMG_Pivot_{print_time}.xlsx"
        
        # Save final table to Excel
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            final_table.to_excel(writer, sheet_name='Pivot', index=False)
        logger.info(f"Excel file created at {output_file}")

        # Apply formatting in Excel
        workbook = openpyxl.load_workbook(output_file)
        ws = workbook['Pivot']

        thin_border = Border(bottom=Side(style='thin'))
        bold_font = Font(bold=True)
        italic_font = Font(italic=True)
        
        # Format headers
        for col_idx in range(1, ws.max_column + 1):
            ws.cell(row=1, column=col_idx).border = Border()

        for col_idx in range(1, ws.max_column + 1):
            ws.cell(row=2, column=col_idx).border = thin_border

        for col in range(1, 5):
            for row in range(1, ws.max_row + 1):
                ws.cell(row=row, column=col).font = bold_font

        # Insert blank column and row
        ws.insert_cols(1)
        ws.insert_rows(1)

        # Adjust column widths
        ws.row_dimensions[3].height = 18.0
        ws.column_dimensions['A'].width = 5.0
        ws.column_dimensions['B'].width = 19.0
        ws.column_dimensions['C'].width = 22.0
        ws.column_dimensions['D'].width = 10.0
        ws.column_dimensions['E'].width = 40.0

        for col in range(6, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col)].width = 9.0

        # Set specific header values
        ws.cell(row=1, column=2).value = f'Version 10: {print_time}'
        ws.cell(row=1, column=2).font = italic_font

        for col in range(1, ws.max_column + 1):
            ws.cell(row=3, column=col).font = bold_font
                
        ws.cell(row=3, column=5).value = 'Component Code Description'
        ws.cell(row=3, column=2).value = 'Branch'
        ws.cell(row=3, column=3).value = 'Site'
        ws.cell(row=3, column=4).value = 'Model'

        workbook.save(output_file)
        logger.info(f"Discrepancy report saved successfully at {output_file}")

    except Exception as e:
        logger.error(f"Error in discrepancy_report function: {e}")
        return
