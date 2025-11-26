"""
Excel QA 引擎
基于 PandasAI 的智能表格问答
"""
import os
from typing import List, Dict, Any, Optional, BinaryIO, Union
from dataclasses import dataclass, field
from io import BytesIO

import pandas as pd

# PandasAI 相关导入
try:
    from pandasai import SmartDataframe, Agent
    from pandasai.llm import LangchainLLM
    PANDASAI_AVAILABLE = True
except ImportError:
    PANDASAI_AVAILABLE = False

import sys
sys.path.insert(0, ".")
from src.llm_factory import create_llm_for_excel
from src.processors.excel_processor import ExcelProcessor, ExcelData


@dataclass
class ExcelResponse:
    """Excel 问答响应"""
    answer: Any  # 可以是字符串、数字、DataFrame 等
    answer_type: str  # text, number, dataframe, chart
    sheet_name: str = ""
    related_rows: List[int] = field(default_factory=list)
    related_columns: List[str] = field(default_factory=list)
    generated_code: str = ""
    error: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        answer = self.answer
        if isinstance(answer, pd.DataFrame):
            answer = answer.to_dict('records')
        
        return {
            "answer": answer,
            "answer_type": self.answer_type,
            "sheet_name": self.sheet_name,
            "related_rows": self.related_rows,
            "related_columns": self.related_columns,
            "generated_code": self.generated_code,
            "error": self.error
        }


class ExcelQAEngine:
    """Excel 问答引擎"""
    
    def __init__(self, llm=None):
        """
        初始化 Excel QA 引擎
        
        Args:
            llm: LLM 实例（可选）
        """
        if not PANDASAI_AVAILABLE:
            raise ImportError("PandasAI 未安装，请运行: uv add pandasai")
        
        self.llm = llm or create_llm_for_excel()
        self.processor = ExcelProcessor()
        
        # 数据存储
        self.excel_data: Optional[ExcelData] = None
        self.smart_dfs: Dict[str, SmartDataframe] = {}
        self.agent: Optional[Agent] = None
        
        # 聊天历史
        self.chat_history: List[Dict[str, str]] = []
    
    def load_file(
        self,
        file: Union[str, BinaryIO],
        filename: str = None
    ) -> Dict[str, Any]:
        """
        加载 Excel/CSV 文件
        
        Args:
            file: 文件路径或文件对象
            filename: 文件名
            
        Returns:
            加载结果信息
        """
        # 处理文件
        self.excel_data = self.processor.process(file, filename)
        
        # 为每个 Sheet 创建 SmartDataframe
        self.smart_dfs = {}
        
        # 包装 LLM
        pandasai_llm = LangchainLLM(self.llm)
        
        all_dfs = []
        for sheet in self.excel_data.sheets:
            # 创建 SmartDataframe
            sdf = SmartDataframe(
                sheet.dataframe,
                name=sheet.name,
                description=f"Excel sheet: {sheet.name}",
                config={
                    "llm": pandasai_llm,
                    "verbose": False,
                    "enable_cache": True,
                    "conversational": True,
                    "save_charts": True,
                    "save_charts_path": "data/charts"
                }
            )
            self.smart_dfs[sheet.name] = sdf
            all_dfs.append(sdf)
        
        # 创建 Agent（支持多表联合查询）
        if len(all_dfs) > 0:
            self.agent = Agent(
                all_dfs,
                config={
                    "llm": pandasai_llm,
                    "verbose": False,
                    "enable_cache": True,
                    "conversational": True
                }
            )
        
        return self.excel_data.to_dict()
    
    def get_sheet_preview(
        self,
        sheet_name: str = None,
        max_rows: int = 10
    ) -> Dict[str, Any]:
        """
        获取 Sheet 预览
        
        Args:
            sheet_name: Sheet 名称，为 None 时返回第一个
            max_rows: 预览行数
            
        Returns:
            预览数据
        """
        if self.excel_data is None:
            return {"error": "未加载文件"}
        
        if sheet_name is None and len(self.excel_data.sheets) > 0:
            sheet_name = self.excel_data.sheets[0].name
        
        sheet = self.excel_data.get_sheet(sheet_name)
        if sheet is None:
            return {"error": f"Sheet '{sheet_name}' 不存在"}
        
        df = sheet.dataframe.head(max_rows)
        
        return {
            "sheet_name": sheet_name,
            "columns": list(df.columns),
            "data": df.to_dict('records'),
            "total_rows": sheet.row_count,
            "total_columns": sheet.column_count
        }
    
    def _parse_response(
        self,
        response: Any,
        sheet_name: str = ""
    ) -> ExcelResponse:
        """
        解析 PandasAI 响应
        
        Args:
            response: PandasAI 返回值
            sheet_name: Sheet 名称
            
        Returns:
            ExcelResponse 对象
        """
        answer_type = "text"
        
        if response is None:
            return ExcelResponse(
                answer="无法生成答案",
                answer_type="error",
                sheet_name=sheet_name,
                error="PandasAI 返回空结果"
            )
        
        if isinstance(response, pd.DataFrame):
            answer_type = "dataframe"
        elif isinstance(response, (int, float)):
            answer_type = "number"
        elif isinstance(response, str):
            # 检查是否是图表路径
            if response.endswith(('.png', '.jpg', '.jpeg', '.svg')):
                answer_type = "chart"
            else:
                answer_type = "text"
        
        return ExcelResponse(
            answer=response,
            answer_type=answer_type,
            sheet_name=sheet_name
        )
    
    def chat(
        self,
        question: str,
        sheet_name: str = None
    ) -> ExcelResponse:
        """
        与 Excel 数据对话
        
        Args:
            question: 用户问题
            sheet_name: 指定的 Sheet 名称（可选）
            
        Returns:
            ExcelResponse 对象
        """
        if self.excel_data is None:
            return ExcelResponse(
                answer="请先加载 Excel 文件",
                answer_type="error",
                error="未加载文件"
            )
        
        try:
            # 如果指定了 Sheet，使用单个 SmartDataframe
            if sheet_name and sheet_name in self.smart_dfs:
                sdf = self.smart_dfs[sheet_name]
                response = sdf.chat(question)
            # 否则使用 Agent 进行多表查询
            elif self.agent:
                response = self.agent.chat(question)
                sheet_name = "多表查询"
            else:
                return ExcelResponse(
                    answer="没有可用的数据",
                    answer_type="error",
                    error="数据未正确加载"
                )
            
            result = self._parse_response(response, sheet_name)
            
            # 记录聊天历史
            self.chat_history.append({
                "role": "user",
                "content": question
            })
            self.chat_history.append({
                "role": "assistant",
                "content": str(result.answer)
            })
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            return ExcelResponse(
                answer=f"处理问题时出错: {error_msg}",
                answer_type="error",
                sheet_name=sheet_name or "",
                error=error_msg
            )
    
    def ask(self, question: str, sheet_name: str = None) -> str:
        """
        简单问答（仅返回答案文本）
        
        Args:
            question: 用户问题
            sheet_name: Sheet 名称
            
        Returns:
            答案文本
        """
        response = self.chat(question, sheet_name)
        
        if response.answer_type == "dataframe":
            return response.answer.to_string()
        return str(response.answer)
    
    def execute_pandas(
        self,
        code: str,
        sheet_name: str = None
    ) -> ExcelResponse:
        """
        直接执行 Pandas 代码
        
        Args:
            code: Pandas 代码
            sheet_name: Sheet 名称
            
        Returns:
            执行结果
        """
        if self.excel_data is None:
            return ExcelResponse(
                answer="请先加载 Excel 文件",
                answer_type="error",
                error="未加载文件"
            )
        
        # 准备执行环境
        local_vars = {"pd": pd}
        
        # 添加所有 DataFrame 到执行环境
        for sheet in self.excel_data.sheets:
            # 使用安全的变量名
            safe_name = sheet.name.replace(" ", "_").replace("-", "_")
            local_vars[safe_name] = sheet.dataframe
            local_vars["df"] = sheet.dataframe  # 默认 df
        
        try:
            exec(code, {"__builtins__": {}}, local_vars)
            result = local_vars.get("result", None)
            
            return self._parse_response(result, sheet_name or "")
            
        except Exception as e:
            return ExcelResponse(
                answer=f"代码执行错误: {str(e)}",
                answer_type="error",
                generated_code=code,
                error=str(e)
            )
    
    def get_column_stats(
        self,
        column: str,
        sheet_name: str = None
    ) -> Dict[str, Any]:
        """
        获取列统计信息
        
        Args:
            column: 列名
            sheet_name: Sheet 名称
            
        Returns:
            统计信息
        """
        if self.excel_data is None:
            return {"error": "未加载文件"}
        
        # 获取 DataFrame
        if sheet_name:
            sheet = self.excel_data.get_sheet(sheet_name)
            if sheet is None:
                return {"error": f"Sheet '{sheet_name}' 不存在"}
            df = sheet.dataframe
        else:
            df = self.excel_data.sheets[0].dataframe if self.excel_data.sheets else None
        
        if df is None or column not in df.columns:
            return {"error": f"列 '{column}' 不存在"}
        
        col_data = df[column]
        
        stats = {
            "column": column,
            "dtype": str(col_data.dtype),
            "count": int(col_data.count()),
            "null_count": int(col_data.isna().sum()),
            "unique_count": int(col_data.nunique())
        }
        
        # 数值列的额外统计
        if pd.api.types.is_numeric_dtype(col_data):
            stats.update({
                "min": float(col_data.min()) if pd.notna(col_data.min()) else None,
                "max": float(col_data.max()) if pd.notna(col_data.max()) else None,
                "mean": float(col_data.mean()) if pd.notna(col_data.mean()) else None,
                "sum": float(col_data.sum()) if pd.notna(col_data.sum()) else None
            })
        
        return stats
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取数据摘要
        
        Returns:
            摘要信息
        """
        if self.excel_data is None:
            return {"error": "未加载文件"}
        
        summary = {
            "filename": self.excel_data.filename,
            "sheet_count": len(self.excel_data.sheets),
            "sheets": []
        }
        
        for sheet in self.excel_data.sheets:
            sheet_info = sheet.to_dict()
            
            # 添加数据类型信息
            dtypes = sheet.dataframe.dtypes.to_dict()
            sheet_info["column_types"] = {k: str(v) for k, v in dtypes.items()}
            
            summary["sheets"].append(sheet_info)
        
        return summary
    
    def clear_history(self) -> None:
        """清空聊天历史"""
        self.chat_history = []
    
    def get_chat_history(self) -> List[Dict[str, str]]:
        """获取聊天历史"""
        return self.chat_history.copy()
    
    def reset(self) -> None:
        """重置引擎"""
        self.excel_data = None
        self.smart_dfs = {}
        self.agent = None
        self.chat_history = []

