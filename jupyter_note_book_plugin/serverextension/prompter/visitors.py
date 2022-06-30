"""
These are AST visitors used primarily by the analysis environment
"""
from astor import dump_tree
from ast import NodeVisitor
from ast import Call, Attribute, Name, Str, Assign, Expr, Num
from ast import Index, Subscript, Slice, ExtSlice, List, Constant
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
    def __init__(self, df_names, new_dfs, pd_alias):

        super().__init__(pd_alias)

        self.df_names = df_names
        self.new_dfs = new_dfs

        self.assign_map = {}  # the mapping of LHS -> RHS
        self.info = {} # map of df_name -> {ancestor_df_or_filename,}

        # we track non_df name references to build an assign map
        # for modelvisitor

        self.context = {"df_refs" : [], "non_df_refs" : []}
         
    def visit_Call(self, node):
        self.generic_visit(node)
        if is_newdata_call(node, self.alias):
            info = get_newdata_info(node, self.alias)
            self.context["df_refs"].append(info["source"])

    def visit_Name(self, node):
        if node.id in self.df_names:
            self.context["df_refs"].append(node.id)
        else:
            self.context["non_df_refs"].append(node.id)

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

        # assign statements are <Left Hand Side, aka targets> = <Right Hand Side, aka value>
        self.route_child(node.value) # this parses the right hand side of the assign statement
        
        # does RHS reference dfs or is there a read_csv call?
        # does LHS reference new_dfs?
        # if RHS and LHS, for each element in LHS add RHS references
        # if RHS but no LHS, do nothing
        # if LHS but no RHS, do nothing

        rhs_has_df = self.context["df_refs"] != []
        rhs_df_names = self.context["df_refs"]
        rhs_non_dfs = self.context["non_df_refs"]


        # search left hand side
        self.context["df_refs"] = []
        self.context["non_df_refs"] = []

        for tgt in node.targets: # this parses the left hand side of the assign statement
            self.route_child(tgt)
        
        lhs_has_df = self.context["df_refs"] != []
        lhs_names = self.context["df_refs"]

        if lhs_has_df and rhs_has_df:
            for name in lhs_names:
                if name not in self.info:
                    self.info[name] = set()
                self.info[name].update(rhs_df_names)
        if lhs_has_df: 
            for name in self.context["non_df_refs"]:
                if name not in self.assign_map:
                    self.assign_map[name] = set()
                self.assign_map[name].add(node.value)

        self.context["df_refs"] = []
        self.context["non_df_refs"] = []
        
    def visit_Expr(self, node):
        self.context["df_refs"] = []
        self.context["non_df_refs"] = []

class ModelScoreVisitor(BaseImportVisitor):

    def __init__(self, pd_alias, model_names, namespace, assign_map):
        super().__init__(pd_alias)
        # strings of known model variable names
        self.model_names = model_names
        self.ns = namespace # mapping of varname -> object
        self.assignments = assign_map # map of name.id -> RHS of assign statement

        self.models = {}
        self.unmatched_call = None

    def is_model_score(self, call_node):
        # test if func node is a call to Classifier.score
        # note that there are other calls to non-clfs and non-model objects 
        # in sklearn. So we need to test if the object is actually a clf name
        if isinstance(call_node.func, Attribute) and call_node.func.attr == "score" and len(call_node.args) > 1:
            if isinstance(call_node.func.value, Name) and call_node.func.value.id in self.model_names:
                return True
            elif isinstance(call_node.func.value, Call):
                # this is ambiguous, use IsSklearnClfVisitor to resolve
                return True
                # TODO: this is a hack and if e.g. someone does
                # something like encoder = OneHotEncoder().fit(X,y), it would
                # treat the OneHotEncoder as a model fit call
            

                # the better way to do things would be to inspect the call 
                # for any references to a list of acceptable module names/functions
                # in sklearn that create classifiers
        return False 
    def visit_Call(self, node):

        self.generic_visit(node)
        
        if self.is_model_score(node): 

            x_cols, df_x_name = self.get_columns(node.args[0])
            y_cols, df_y_name = self.get_columns(node.args[1])

            open_names = [n for n in self.models.keys() if self.models[n] == {}]
            
            if open_names:
                name = open_names.pop()
                self.models[name] = {"x" : x_cols, "y" : y_cols, 
                                     "x_df" : df_x_name, "y_df" : df_y_name}
            else:
                self.unmatched_call = {"x" : x_cols, "y" : y_cols,
                                       "x_df" : df_x_name, "y_df" : df_y_name}

    def visit_Assign(self, node): 

        self.generic_visit(node)
        open_names = [n for n in self.models.keys() if self.models[n] == {}]

        if open_names and self.unmatched_call: 

            name = open_names.pop()
            self.models[name] = self.unmatched_call
            self.unmatched_call = None
 
    def visit_Name(self, node):
        if node.id in self.model_names and node.id not in self.models.keys():
            self.models[node.id] = {}

    def get_columns(self, node):

        visitor = ColumnVisitor(self.ns, self.assignments)
        visitor.visit(node)

        return visitor.cols, visitor.df_name

class ModelFitVisitor(ModelScoreVisitor):
    def __init__(self, pd_alias, model_names, namespace, assign_map):
        super().__init__(pd_alias, model_names, namespace, assign_map)
    
    def is_model_fit(self, call_node):
        # if this is a function node, check to see if it is a call to 
        # Classifier.fit. Note unlike is_model_score, we want to check 
        # calls to non-clfs
        if isinstance(call_node.func, Attribute) and call_node.func.attr == "fit" and len(call_node.args) >= 1:
            # if this fit call is a variable name, we want it
            if isinstance(call_node.func.value, Name) and call_node.func.value.id in self.model_names:
                return True
        elif isinstance(call_node.func, Call):
            # if it's not a variable, but still a SomethingClassifier.fit call, 
            # we want that too. Unfortunately, scikit learn is DuckTyped. 
            # Things that "fit" just happen to have a fit function without 
            # inheriting from the same base class

            classname = str.lower(call_node.func.value.attr)

            # this should get most of them
            if "classifier" in classname or "regress" in classname or "forest" \
            in classname or "tree" in classname or "lars" in classname or \
            "elastic" in classname or "ridge" in classname or "perceptron" or \
            "enet" in classname:
                return True 
        return False

    def visit_Call(self, node):
        self.generic_visit(node)
        
        if self.is_model_fit(node):
            X_cols, X_df_name = self.get_columns(node.args[0])
            y_cols = None
            y_df_name = None
            if len(node.args) > 1:
                y_cols, y_df_name = self.get_columns(node.args[1])
            
            open_names = [n for n in self.models.keys() if self.models[n] == {}]
            
            if open_names:
                name = open_names.pop()
                self.models[name] = {"X" : X_cols, "y" : y_cols if y_cols is not None else "__None", 
                                     "X_df" : X_df_name, "y_df" : y_df_name if y_df_name is not None else "__None"}
            else:
                self.unmatched_call = {"X" : X_cols, "y" : y_cols if y_cols is not None else "__None",
                                       "X_df" : y_df_name, "y_df" : y_df_name if y_df_name is not None else "__None"}


class ColumnVisitor(NodeVisitor):
    """
    This has the job of, given a node, trying to find the
    column names, if any, of the resulting dataframe
    """

    def __init__(self, ns, assignments):
        # dfs is a dict where varname -> dataframe object
        self.ns = ns

        # mapping of name id -> RHS of assign statements
        self.assign_vals = assignments

        # written to during parsing
        self.refs_df = False # is there a read from a dataframe type object?
        self.cols = None # what are the active columns?
        self.df_name = None

        self.df_func_handlers = [
            DropNaHandler(self.ns),
            ToNumpyHandler(self.ns),
            DropHandler(self.ns),
        ]

    def visit_Call(self, node):

        self.generic_visit(node)

        if self.refs_df:
            for handler in self.df_func_handlers:
                if handler.match(node):
                    self.cols = handler.adjust(self.cols, node, self.ns[self.df_name])

    def parse_regular(self, node):
        # parse a subscript node referencing things like df["a"], df["a" : "c"], df[["a","b"]]
        if isinstance(node.slice, Index) and isinstance(node.slice.value, Str):
            if node.slice.value.s in self.cols:
                self.cols = [node.slice.value.s] 
        if isinstance(node.slice, Index) and isinstance(node.slice.value, Num):
            if node.slice.value.n in self.cols:
                self.cols = [node.slice.value.n]
        if isinstance(node.slice, Index) and isinstance(node.slice.value, List):
            # try resolving to strings
            poss_selected = resolve_list(self.ns, node.slice.value)
            if all([col_name in self.cols for col_name in poss_selected]):
                self.cols = poss_selected
        if isinstance(node.slice, Index) and isinstance(node.slice.value, Name):
            # need to try to resolve name (may be boolean array, normal list of strings)
            ref_obj = self.ns[node.slice.value.id]
            if hasattr(ref_obj, "__iter__"):
                if all([obj in self.cols for obj in ref_obj]):
                    self.cols = list(ref_obj)
            else:
                if ref_obj in self.cols:
                    self.cols = [ref_obj]
        if isinstance(node.slice, List):
            poss_selected = resolve_list(self.ns, node.slice)
            self.cols = poss_selected
        if isinstance(node.slice, Constant):
            self.cols = [node.slice.value]
    def parse_loc(self, node):
        """
        node is a subscript where the main item references the loc attribute
        """
        if isinstance(node.slice, ExtSlice):
            # then we know the second element indexes columns
            col_index_node = node.slice.dims[-1]
        elif isinstance(node.slice, Index):
            if isinstance(node.slice.value, Tuple):
                col_index_node = node.slice.value.elts[-1]
            else:
                col_index_node = node.slice.value
        else:
            return
        if isinstance(col_index_node, List):
            poss_selected = resolve_list(self.ns, col_index_node)
            if all([col_name in self.cols for col_name in poss_selected]):
                self.cols = poss_selected
        if isinstance(col_index_node, Name):
            ref_obj = self.ns[col_index_node.id]
            if hasattr(ref_obj, "__iter__"):
                if all([obj in self.cols for obj in ref_obj]):
                    self.cols = list(ref_obj)
            else:
                if ref_obj in self.cols:
                    self.cols = [ref_obj]
        if isinstance(col_index_node, Str):
            if col_index_node.s in self.cols:
                self.cols = [col_index_node.s]
        if isinstance(col_index_node, Num): 
            if col_index_node.n in self.cols:
                self.cols = [col_index_node.n]
    def parse_iloc(self, node):
        pass
#    def visit_Assign(self, node):
    def visit_Subscript(self, node):
        self.generic_visit(node)

        if not self.refs_df:
            return

        if isinstance(node.value, Attribute) and node.value.attr == "loc":
            self.parse_loc(node)
        elif isinstance(node.value, Attribute) and node.value.attr == "iloc":
            self.parse_iloc(node)
        else:   
            self.parse_regular(node)

    def visit_Attribute(self, node):
        self.generic_visit(node)
    def visit_Name(self, node):

        if node.id in self.ns.keys():
            if isinstance(self.ns[node.id], pd.DataFrame):
                self.refs_df = True
                self.df_name = node.id
                self.cols = list(self.ns[node.id].columns)
            if isinstance(self.ns[node.id], pd.Series):
                self.refs_df = True
                self.df_name = node.id
                self.cols = [self.ns[node.id].name]
        if not self.refs_df and node.id in self.assign_vals.keys():
            for rhs in self.assign_vals[node.id]:
                self.visit(rhs)
        #print("visited name {0}, refs_df {1}, df_name {2}, cols {3}".format(node.id, self.refs_df, self.df_name, self.cols))
class CallHandler:
    """
    class for handling instances where dataframe type object is called
    """
    def __init__(self, namespace):
        self.ns = namespace

    def match(self, node):
        """is node a call to the type of function the implementing class is meant to handle?"""
        raise NotImplementedError
    def adjust(self, columns, node, df):
        """returns a list of columns in dataframe after call on dataframe of specific function"""
        raise NotImplementedError

class ToNumpyHandler(CallHandler):
    def match(self, node):
        return isinstance(node.func, Attribute) and node.func.attr == "to_numpy"
    def adjust(self, columns, node, df):
        return columns

class DropNaHandler(CallHandler):

    def match(self, node):
        return isinstance(node.func, Attribute) and node.func.attr == "dropna"

    def adjust(self, columns, node, df):

        keywords = {k.arg : k.value for k in node.keywords}

        if "axis" in keywords:
            axis = keywords["axis"].n
        else:
            axis = 0
        if axis == 0:
            return columns

        if "inplace" in keywords:
            inplace = keywords["inplace"].value
        else:
            inplace = False
        if inplace:
            return []
        
        if "subset" in keywords:
            if isinstance(keywords["subset"], List):
                subset = []
                for elt in keywords["subset"].elts:
                    if isinstance(elt, Str):
                        subset.append(elt.s)
                    elif isinstance(elt, Name) and elt.id in self.ns:
                        subset.append(self.ns[elt.id])
 
            elif isinstance(keywords["subset"], Name) and keywords["subset"].id in self.ns:
                subset = self.ns[keywords["subset"]]
            else:
                subset = None
        else:
            subset = None 
        
        if "how" in keywords:
            how = keywords["how"].value
        else:
            how = "any"

        if "thresh" in keywords:
            thresh = keywords["thresh"].n
        else:   
            thresh = None
        return df[columns].dropna(subset=subset, how=how, thresh=thresh).columns
class DropHandler(CallHandler):
    
    def match(self, node):
        return isinstance(node.func, Attribute) and node.func.attr == "drop"

    def adjust(self, columns, node, df):

        keywords = {k.arg : k.value for k in node.keywords}

        if "axis" in keywords:
            axis = keywords["axis"].n
        else:
            axis = 0
        if axis == 0 and "columns" not in keywords:
            return columns

        if "inplace" in keywords:
            inplace = keywords["inplace"].value
        else:
            inplace = False
        if inplace:
            return []

        drop_labels = []
        drop_columns = []

        if "columns" in keywords:
            if isinstance(keywords["columns"], Str):
                drop_columns = [keywords["columns"].s]
            elif isinstance(keywords["columns"], Name) and keywords["columns"].id in self.ns:
                drop_columns = [self.ns[keywords["columns"].id]] 
            elif isinstance(keywords["columns"], List):
                drop_columns = resolve_list(self.ns, keywords["columns"])
        if "labels" in keywords:
            if isinstance(keywords["labels"], Str):
                drop_labels = [keywords["labels"].s]
            elif isinstance(keywords["labels"], Name) and keywords["labels"].id in self.ns:
                drop_labels = [self.ns[keywords["labels"].id]] 
            elif isinstance(keywords["labels"], List):
                drop_labels = resolve_list(self.ns, keywords["labels"])

        if not drop_columns and not drop_labels:
            arg = node.args[0]
            if isinstance(arg, Str):
                drop_columns = [arg.s]
            elif isinstance(arg, Name) and arg.id in self.ns:
                drop_columns = [self.ns[arg.id]] 
            elif isinstance(arg, List):
                drop_columns = resolve_list(self.ns, arg)
        return [c for c in columns if c not in drop_columns + drop_labels]
 
def resolve_list(namespace, list_node):
    output = []
    for elt in list_node.elts:
        if isinstance(elt, Name) and elt.id in namespace:
            output.append(namepsace[elt.id])
        elif isinstance(elt, Str):
            output.append(elt.s)
        elif isinstance(elt, NameConstant):
            output.append(elt.value)
        elif isinstance(elt, Num):
            output.append(elt.n)

    return output 
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
