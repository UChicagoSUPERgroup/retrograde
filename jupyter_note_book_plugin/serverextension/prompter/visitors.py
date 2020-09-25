"""
These are AST visitors used primarily by the analysis environment
"""

from ast import NodeVisitor
from ast import Call, Attribute, Name, Str, Assign, Expr

import pandas as pd

PD_READ_FUNCS = ["read_csv", "read_fwf", "read_json", "read_html",
                 "read_clipboard", "read_excel", "read_hdf",
                 "read_feather", "read_parquet", "read_orc",
                 "read_msgpack", "read_stata", "read_sas",
                 "read_spss", "read_pickle", "read_sql",
                 "read_gbq"]

class BaseImportVisitor(NodeVisitor):
    """handle things like import * as x,  etc"""
    def __init__(self, alias):
        super().__init__()
        self.alias = alias

    def visit_Import(self, node):
        for alias in node.names:
            self.alias.add_import(alias)
    def visit_ImportFrom(self, node):
        module_name = node.module
        for alias in node.names:
            self.alias.add_importfrom(module_name, alias)

class DataFrameVisitor(BaseImportVisitor):

    """
    This class visits code and identifies where dataframe type objects
    are referenced
    
    It returns information about information like source on a best
    effort basis
    """

    def __init__(self, df_names, pd_alias):

        super().__init__(pd_alias)
        self.df_names = df_names

        self.assign_map = {}  # the mapping of LHS -> RHS
        self.info = {} # information about the data

        self.context = {"info" : [], "df_names" : [], "non_df_names" : []}
         
    def visit_Call(self, node):
        self.generic_visit(node)
        if is_newdata_call(node, self.alias):
            info = get_newdata_info(node, self.alias)
            self.context["info"].append(info)

    def visit_Name(self, node):
        if node.id in self.df_names:
            self.context["df_names"].append(node.id)
        else:
            self.context["non_df_names"].append(node.id)

    def route_child(self, node):
        # since calling generic_visit(node) skips node this includes node 
        # in subsequent analysis
        if isinstance(node, Assign):
            self.visit_Assign(node)
        elif isinstance(node, Name):
            self.visit_Name(node)
        elif isinstance(node, Call):
            self.visit_Call(node)
        elif isinstance(node, Expr):
            self.visit_Expr(node)
        else:
            self.generic_visit(node)

    def visit_Assign(self, node):
        self.route_child(node.value)

        rhs_has_df = self.context["df_names"] != []
        rhs_df_names = self.context["df_names"]
        rhs_non_dfs = self.context["non_df_names"]

        self.context["df_names"] = []
        self.context["non_df_names"] = []

        for tgt in node.targets: 
            self.route_child(tgt)
        lhs_has_df = self.context["df_names"] != []
        lhs_names = self.context["df_names"]

        if lhs_has_df and not rhs_has_df:
            # match info to name 
            for name in lhs_names:
                if self.context["info"] != []:
                    info = self.context["info"].pop()
                    self.info[name] = info
        if not lhs_has_df:
            for name in self.context["non_df_names"]:
                try:
                    self.assign_map[name].update(rhs_df_names)
                    self.assign_map[name].update(rhs_non_dfs)
                except KeyError:
                    self.assign_map[name] = set()
                    self.assign_map[name].update(rhs_df_names)
                    self.assign_map[name].update(rhs_non_dfs)

        self.context["df_names"] = []
        self.context["non_df_names"] = []
        self.context["info"] = []
        
    def visit_Expr(self, node):
        self.context["info"] = []
        self.context["df_names"] = []
        self.context["non_df_names"] = []
# class ModelVisitor(BaseImportVisitor):
    
def is_newdata_call(node, pd_alias):
    """
    is node a read_* type function?
    """
    if not isinstance(node, Call):
        return False

    func = node.func

    if isinstance(func, Name):
        for read_func in PD_READ_FUNCS:
            if read_func in pd_alias.func_mapping and pd_alias.func_mapping[read_func] == func.id:
                return True
    elif isinstance(func, Attribute):
        if func.attr in PD_READ_FUNCS:
            return True
    return False            

def get_newdata_info(node, alias):
    source = as_string(node.args[0])
    if isinstance(node.func, Name):
        if node.func.id not in PD_READ_FUNCS:
            func_name = alias.get_alias_for(node.func.id)
            fmt = func_name.split("_")[-1]
        else:
            fmt = node.func.id.split("_")[-1]
    if isinstance(node.func, Attribute):
        fmt = node.func.attr.split("_")[-1]
    return {"source" : source, "format" : fmt} 

def as_string(name_or_attrib):
    """print as string name or attribute"""
    if isinstance(name_or_attrib, Attribute):
        full = name_or_attrib.attr
        curr = name_or_attrib

        while isinstance(curr, Attribute):
            curr = curr.value
            if isinstance(curr, Attribute):
                full = curr.attr+"."+full
            elif isinstance(curr, Name):
                full = curr.id+"."+full
        return full
    if isinstance(name_or_attrib, Name):
        return name_or_attrib.id
    if isinstance(name_or_attrib, Str):
        return name_or_attrib.s
    return ""
