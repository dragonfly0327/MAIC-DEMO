import pandas as pd
import numpy as np
from utils import SPECIAL_SELECTION_COLUMNS

class BOMProcessor:
    """
    Encapsulates data processing and parsing operations for BOMs.
    """
    def __init__(self, logger, df: pd.DataFrame, special_column_selections: dict[str, any], dynamic_mapping: dict[str, any], assembly_moqs: dict, email_subject, cust_name="", rfq_num=""):
        self.logger = logger
        self.df = df
        self.special_column_selections = special_column_selections
        self.dynamic_mapping = dynamic_mapping
        self.assembly_moqs = assembly_moqs
        self.standard_columns = ['Assy Level', 'Comp Level', 'Assy #', 'Assy Model', 'Assy Rev', 'Part', 'Description', 'MFR', 'MPN', 'Qty', 'UOM']
        self.email_subject = email_subject
        self.cust_name = cust_name
        self.rfq_num = rfq_num

    @staticmethod
    def parse_sparse_bom(df: pd.DataFrame) -> pd.DataFrame:
        """
        Handles sparse BOM layouts where assembly headers only appear on the first row of a block.
        Fills forward 'Assy #', 'Assy Model', and 'Assy Rev' for all constituent rows.
        """
        current_assy = None
        current_model = None
        current_rev = None
        
        parsed_rows = []
        for _, row in df.iterrows():
            row_assy = str(row.get('Assy #', '')).strip()
            if row_assy and row_assy.lower() != 'nan' and row_assy.lower() != 'assy #':
                current_assy = row_assy
                current_model = str(row.get('Assy Model', '')).strip()
                current_rev = str(row.get('Assy Rev', '')).strip()
            
            new_row = row.copy()
            new_row['Assy #'] = current_assy if current_assy else ""
            new_row['Assy Model'] = current_model if current_model else ""
            new_row['Assy Rev'] = current_rev if current_rev else ""
            parsed_rows.append(new_row)
            
        return pd.DataFrame(parsed_rows)

    @staticmethod
    def _AssignLevel(df: pd.DataFrame) -> pd.DataFrame:
        dummy_df = df.copy()
        dummy_df['Assy #'] = dummy_df['Assy #'].astype(str).str.strip()
        
        dummy_df['Comp Count'] = dummy_df.groupby('Assy #').cumcount() + 1
        dummy_df = dummy_df.sort_values(by=['Assy #', 'Comp Count'], ascending=[True, True])
        dummy_df = dummy_df.drop('Comp Count', axis=1)

        final_df = dummy_df
        if 'Comp Level' not in final_df.columns:
            final_df.insert(0, column='Comp Level', value=None)
        if 'Assy Level' not in final_df.columns:
            final_df.insert(0, column='Assy Level', value=None)
            
        final_df['Assy Level'] = final_df['Assy #'].factorize()[0] + 1
        comp_count = final_df.groupby('Assy #').cumcount() + 1
        final_df['Comp Level'] = final_df['Assy Level'].astype(str) + '.' + comp_count.astype(str)
        
        return final_df

class DataLoader:
    """
    Handles reading the raw Excel file and performing the initial header mapping.
    """
    @staticmethod
    def get_excel_headers(file_path):
        try:
            df_header_only = pd.read_excel(file_path, nrows=1, header=0)
            actual_excel_headers = [
                str(col).strip() for col in df_header_only.columns
                if str(col).strip() and not str(col).startswith('Unnamed:') and not pd.isna(col)
            ]
            return actual_excel_headers
        except pd.errors.EmptyDataError:
            raise ValueError("The Excel file is empty or contains no readable data.")
        except Exception as e:
            raise ValueError(f"Failed to read headers from Excel file: {e}")

    @staticmethod
    def load_and_map_dataframe(file_path, special_column_selections, dynamic_mapping, standard_columns, multi_source_columns):
        try:
            df_full = pd.read_excel(file_path, header=0)
            
            for col_name, selection in special_column_selections.items():
                if selection['method'] == 'map':
                    source_col = selection['source_column']
                    if source_col in df_full.columns:
                        df_full = df_full.rename(columns={source_col: col_name})
                    else:
                        raise ValueError(f"Selected column '{source_col}' for '{col_name}' not found in Excel file.")
                elif selection['method'] == 'fixed':
                    df_full[col_name] = selection['value']
            
            df_processed = df_full.copy()
            special_mapped_sources = {s['source_column'] for s in special_column_selections.values() if s['method'] == 'map'}
            
            for target_col, sources in dynamic_mapping.items():
                if target_col in multi_source_columns:
                    if isinstance(sources, list) and sources:
                        effective_sources = [s for s in sources if s in df_full.columns and s not in special_mapped_sources]
                        if not effective_sources:
                            df_processed[target_col] = np.nan
                            print(f"Warning: No valid source columns found for multi-source '{target_col}'. Column will be empty.")
                            continue
                            
                        df_processed[target_col] = df_full[effective_sources].fillna('').astype(str).agg(
                            lambda x: ', '.join(filter(None, x)), axis=1
                        )
                    else:
                        df_processed[target_col] = np.nan
                else:
                    if isinstance(sources, str) and sources in df_full.columns and sources not in special_mapped_sources:
                        df_processed[sources] = df_processed[sources] # Keep reference
                        # We will rename later or index directly
            
            final_df = pd.DataFrame()
            for col_name in special_column_selections.keys():
                if col_name in df_processed.columns:
                    final_df[col_name] = df_processed[col_name]
                else:
                    final_df[col_name] = np.nan

            for col_name in multi_source_columns:
                if col_name in dynamic_mapping and isinstance(dynamic_mapping[col_name], list):
                    if col_name in df_processed.columns:
                        final_df[col_name] = df_processed[col_name]
                    else:
                        final_df[col_name] = np.nan

            for standard_col in standard_columns:
                if standard_col in SPECIAL_SELECTION_COLUMNS:
                    continue
                if standard_col in multi_source_columns:
                    continue
                
                actual_header_for_std_col = None
                for actual_h, mapped_std_col in dynamic_mapping.items():
                    if mapped_std_col == standard_col:
                        actual_header_for_std_col = actual_h
                        break
                
                if actual_header_for_std_col and actual_header_for_std_col in df_full.columns:
                    if actual_header_for_std_col not in special_mapped_sources:
                        final_df[standard_col] = df_full[actual_header_for_std_col]
                    else:
                        final_df[standard_col] = np.nan
                else:
                    final_df[standard_col] = np.nan

            df_final = final_df.reindex(columns=standard_columns).copy()
            return df_final
        except Exception as e:
            raise ValueError(f"Failed to process Excel data: {e}")

def export_dataframe(dataframes_with_sheetnames, output_file_path):
    try:
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            for sheet_name, df in dataframes_with_sheetnames.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"Successfully exported data to {output_file_path} with sheets: {', '.join(dataframes_with_sheetnames.keys())}")
    except Exception as e:
        raise ValueError(f"Failed to export data to Excel: {e}")
