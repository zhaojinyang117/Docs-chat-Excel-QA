"""
Excel 预处理器
处理合并单元格、多级表头、多 Sheet 等复杂情况
"""
import os
import tempfile
from typing import List, Dict, Any, Optional, BinaryIO, Union, Tuple
from io import BytesIO
from dataclasses import dataclass, field

import pandas as pd
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

import sys
sys.path.insert(0, ".")


@dataclass
class SheetData:
    """单个 Sheet 的数据"""
    name: str
    dataframe: pd.DataFrame
    row_count: int
    column_count: int
    columns: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": self.columns
        }


@dataclass
class ExcelData:
    """Excel 文件数据"""
    filename: str
    sheets: List[SheetData] = field(default_factory=list)
    
    def get_sheet(self, name: str) -> Optional[SheetData]:
        """根据名称获取 Sheet"""
        for sheet in self.sheets:
            if sheet.name == name:
                return sheet
        return None
    
    def get_all_dataframes(self) -> Dict[str, pd.DataFrame]:
        """获取所有 DataFrame"""
        return {sheet.name: sheet.dataframe for sheet in self.sheets}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "sheet_count": len(self.sheets),
            "sheets": [s.to_dict() for s in self.sheets]
        }


class ExcelProcessor:
    """Excel 预处理器"""
    
    def __init__(self):
        """初始化 Excel 处理器"""
        pass
    
    def _fix_merged_cells(self, ws: Worksheet) -> None:
        """
        修复合并单元格
        将合并单元格的值填充到所有子单元格
        
        Args:
            ws: openpyxl Worksheet 对象
        """
        # 获取所有合并区域的副本（因为要在遍历时修改）
        merged_ranges = list(ws.merged_cells.ranges)
        
        for merged_range in merged_ranges:
            # 获取左上角单元格的值
            top_left_cell = ws.cell(merged_range.min_row, merged_range.min_col)
            top_left_value = top_left_cell.value
            
            # 解除合并
            ws.unmerge_cells(str(merged_range))
            
            # 填充所有单元格
            for row in range(merged_range.min_row, merged_range.max_row + 1):
                for col in range(merged_range.min_col, merged_range.max_col + 1):
                    ws.cell(row, col, top_left_value)
    
    def _flatten_multi_index_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        扁平化多级表头
        将 ('2023', 'Q1') 转换为 '2023_Q1'
        
        Args:
            df: DataFrame
            
        Returns:
            处理后的 DataFrame
        """
        if isinstance(df.columns, pd.MultiIndex):
            # 将多级列名连接为单层
            df.columns = ['_'.join(map(str, col)).strip('_') for col in df.columns.values]
        return df
    
    def _clean_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清理列名
        
        Args:
            df: DataFrame
            
        Returns:
            处理后的 DataFrame
        """
        # 去除列名中的空白字符
        df.columns = [str(col).strip() if col is not None else f'Column_{i}' 
                      for i, col in enumerate(df.columns)]
        
        # 处理重复列名
        seen = {}
        new_columns = []
        for col in df.columns:
            if col in seen:
                seen[col] += 1
                new_columns.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                new_columns.append(col)
        df.columns = new_columns
        
        return df
    
    def _detect_header_row(self, ws: Worksheet, max_rows: int = 10) -> int:
        """
        自动检测表头行
        
        Args:
            ws: Worksheet 对象
            max_rows: 检查的最大行数
            
        Returns:
            表头行索引（0-based）
        """
        # 简单策略：找第一个非空且大部分单元格有值的行
        for row_idx in range(1, min(max_rows + 1, ws.max_row + 1)):
            row_values = [ws.cell(row_idx, col).value for col in range(1, ws.max_column + 1)]
            non_empty = sum(1 for v in row_values if v is not None and str(v).strip())
            
            # 如果超过一半的单元格有值，认为是表头
            if non_empty > len(row_values) / 2:
                return row_idx - 1  # 转换为 0-based
        
        return 0
    
    def _remove_empty_rows_and_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        移除空行和空列
        
        Args:
            df: DataFrame
            
        Returns:
            处理后的 DataFrame
        """
        # 移除全空行
        df = df.dropna(how='all')
        
        # 移除全空列
        df = df.dropna(axis=1, how='all')
        
        # 重置索引
        df = df.reset_index(drop=True)
        
        return df
    
    def process_file(
        self,
        file: Union[str, BinaryIO],
        filename: str = None,
        fix_merged: bool = True,
        flatten_headers: bool = True,
        detect_header: bool = True
    ) -> ExcelData:
        """
        处理 Excel 文件
        
        Args:
            file: 文件路径或文件对象
            filename: 文件名
            fix_merged: 是否修复合并单元格
            flatten_headers: 是否扁平化多级表头
            detect_header: 是否自动检测表头行
            
        Returns:
            ExcelData 对象
        """
        # 处理文件输入
        if hasattr(file, 'read'):
            file_content = file.read()
            if hasattr(file, 'seek'):
                file.seek(0)
            file_buffer = BytesIO(file_content)
            actual_filename = filename or getattr(file, 'name', 'unknown.xlsx')
        else:
            with open(file, 'rb') as f:
                file_content = f.read()
            file_buffer = BytesIO(file_content)
            actual_filename = filename or os.path.basename(file)
        
        sheets_data = []
        
        if fix_merged:
            # 使用 openpyxl 处理合并单元格
            wb = load_workbook(file_buffer)
            
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                
                # 修复合并单元格
                self._fix_merged_cells(ws)
            
            # 保存到新的 buffer
            output_buffer = BytesIO()
            wb.save(output_buffer)
            output_buffer.seek(0)
            file_buffer = output_buffer
        
        # 使用 pandas 读取所有 sheet
        excel_file = pd.ExcelFile(file_buffer)
        
        for sheet_name in excel_file.sheet_names:
            try:
                # 先尝试读取以检测表头
                if detect_header:
                    # 先不指定 header，读取原始数据
                    df_raw = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
                    
                    # 简单的表头检测：检查第一行是否像表头
                    first_row = df_raw.iloc[0] if len(df_raw) > 0 else []
                    is_header = all(
                        isinstance(v, str) or pd.isna(v) 
                        for v in first_row
                    )
                    
                    if is_header:
                        df = pd.read_excel(excel_file, sheet_name=sheet_name, header=0)
                    else:
                        df = df_raw
                        df.columns = [f'Column_{i}' for i in range(len(df.columns))]
                else:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                
                # 扁平化多级表头
                if flatten_headers:
                    df = self._flatten_multi_index_columns(df)
                
                # 清理列名
                df = self._clean_column_names(df)
                
                # 移除空行空列
                df = self._remove_empty_rows_and_cols(df)
                
                if len(df) > 0:
                    sheet_data = SheetData(
                        name=sheet_name,
                        dataframe=df,
                        row_count=len(df),
                        column_count=len(df.columns),
                        columns=list(df.columns)
                    )
                    sheets_data.append(sheet_data)
                    
            except Exception as e:
                print(f"处理 Sheet '{sheet_name}' 时出错: {e}")
                continue
        
        return ExcelData(
            filename=actual_filename,
            sheets=sheets_data
        )
    
    def process_csv(
        self,
        file: Union[str, BinaryIO],
        filename: str = None,
        encoding: str = None
    ) -> ExcelData:
        """
        处理 CSV 文件
        
        Args:
            file: 文件路径或文件对象
            filename: 文件名
            encoding: 文件编码
            
        Returns:
            ExcelData 对象
        """
        # 获取文件名
        if filename is None:
            if hasattr(file, 'name'):
                filename = file.name
            elif isinstance(file, str):
                filename = os.path.basename(file)
            else:
                filename = 'unknown.csv'
        
        # 尝试不同编码读取
        encodings = [encoding] if encoding else ['utf-8', 'gbk', 'gb2312', 'latin-1']
        
        df = None
        for enc in encodings:
            try:
                if hasattr(file, 'read'):
                    content = file.read()
                    if hasattr(file, 'seek'):
                        file.seek(0)
                    if isinstance(content, bytes):
                        content = content.decode(enc)
                    df = pd.read_csv(BytesIO(content.encode('utf-8')))
                else:
                    df = pd.read_csv(file, encoding=enc)
                break
            except (UnicodeDecodeError, Exception):
                continue
        
        if df is None:
            raise ValueError("无法读取 CSV 文件，请检查文件编码")
        
        # 清理
        df = self._clean_column_names(df)
        df = self._remove_empty_rows_and_cols(df)
        
        sheet_data = SheetData(
            name="Sheet1",
            dataframe=df,
            row_count=len(df),
            column_count=len(df.columns),
            columns=list(df.columns)
        )
        
        return ExcelData(
            filename=filename,
            sheets=[sheet_data]
        )
    
    def process(
        self,
        file: Union[str, BinaryIO],
        filename: str = None
    ) -> ExcelData:
        """
        自动处理 Excel 或 CSV 文件
        
        Args:
            file: 文件路径或文件对象
            filename: 文件名
            
        Returns:
            ExcelData 对象
        """
        # 获取文件名
        if filename is None:
            if hasattr(file, 'name'):
                filename = file.name
            elif isinstance(file, str):
                filename = os.path.basename(file)
            else:
                filename = 'unknown'
        
        ext = filename.lower().split('.')[-1]
        
        if ext in ['xlsx', 'xls']:
            return self.process_file(file, filename)
        elif ext == 'csv':
            return self.process_csv(file, filename)
        else:
            raise ValueError(f"不支持的文件类型: {ext}")
    
    def rows_to_text(
        self,
        df: pd.DataFrame,
        sheet_name: str = "Sheet1",
        max_rows: int = None
    ) -> List[Dict[str, Any]]:
        """
        将 DataFrame 行转换为文本描述
        用于向量化搜索
        
        Args:
            df: DataFrame
            sheet_name: Sheet 名称
            max_rows: 最大行数
            
        Returns:
            行文本列表，每个元素包含 text 和 metadata
        """
        results = []
        rows_to_process = df.head(max_rows) if max_rows else df
        
        for idx, row in rows_to_process.iterrows():
            # 构建行描述
            parts = []
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    parts.append(f"{col}: {value}")
            
            text = ", ".join(parts)
            
            results.append({
                "text": text,
                "metadata": {
                    "sheet": sheet_name,
                    "row": int(idx) + 2,  # Excel 行号从 1 开始，加上表头
                    "columns": list(df.columns)
                }
            })
        
        return results

