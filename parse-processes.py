import os
from pathlib import Path
import ast
import json
from pprint import pprint


JS_PROCESS_TEMPLATE = """
class NoSlipProcess {
    constructor()
    {
        this.addInput("model_part","string");
        this.addOutput("Process","process");
        this.properties = {
            "model_part_name" : ""
        };

        this.size = this.computeSize();
    }

    onExecute()
    {
        output = {
            "python_module" : "apply_noslip_process",
            "kratos_module" : "KratosMultiphysics.FluidDynamicsApplication"
        }
        output["Parameters"] = this.properties
        output["Parameters"]["model_part_name"] = this.getInputData(0)
        this.setOutputData(0, output);
    }
}

NoSlipProcess.title = "No-slip process";
NoSlipProcess.desc = "Node to specify a no-slip boundary process.";

LiteGraph.registerNodeType("processes/NoSlipProcess", NoSlipProcess);
"""

def get_children_by_type(node, ntype):
    #  return a list of children nodes if the requested type
    children = []
    for n in ast.iter_child_nodes(node):
        if isinstance(n, ntype):
            children.append(n)
    return children


def get_child_by_type_and_name(nodes, ctype, name):
    #  return the requested node (by name)
    for node in ast.iter_child_nodes(nodes):
        if isinstance(node, ctype):
            if name in node.name:
                return node


def get_default_params_from_process(code):
    # HEURISTICA:
    # . Busca el argumento del "return" de la funcion "Factory"
    # . Busca la clase con el nombre del return en "Factory"
    # . Busca "__init__"
    # . Buscar el nombre del argumento de "ValidateAndAssingDefaults" (default_settings)
    # . Busca los settings por dafault y saca el string
    main_node = ast.parse(code)
    node = get_child_by_type_and_name(main_node, ast.FunctionDef, "Factory")
    node = get_children_by_type(node, ast.Return)[0]
    class_name = node.value.func.id
    node = get_child_by_type_and_name(main_node, ast.ClassDef, class_name)
    init_node = get_child_by_type_and_name(node, ast.FunctionDef, "__init__")
    # print(f"Found init: {init_node.name}")
    varname = init_node.args.args[-1].arg
    # print(f"Found variable name: {varname}")

    call_nodes = []
    for node in get_children_by_type(init_node, ast.Expr):
        call_nodes.extend(get_children_by_type(node, ast.Call))
    for n in call_nodes:
        try:
            if varname in n.func.value.id:
                defaults = n.args[0].id
        except:
            pass
    # print(f"Found default settings name: {defaults}")

    # PARSE:
    # default_settings = KratosMultiphysics.Parameters("""{...}""")
    # AST:
    # Module(
    #     body=[
    #         Assign(
    #             targets=[
    #                 Name(id='default_settings', ctx=Store())],
    #             value=Call(
    #                 func=Attribute(
    #                     value=Name(id='KratosMultiphysics', ctx=Load()),
    #                     attr='Parameters',
    #                     ctx=Load()),
    #                 args=[
    #                     Constant(value='{...}')],
    #                 keywords=[]))],
    #     type_ignores=[])

    for node in get_children_by_type(init_node, ast.Assign):
        try:
            if defaults in node.targets[0].id:
                return node.value.args[0].value
        except:
            return "{}"


BASE = [x for x in os.getenv("PYTHONPATH").split(":") if "Kratos/bin" in x][0]
PATHS = (Path(BASE) / "KratosMultiphysics").glob("**/*_process.py")

DATA = []
notparsed = []
for p in PATHS:
    code = p.read_text()
    try:
        params = json.loads(get_default_params_from_process(p.read_text()))
        process_data = {
            "group": p.parents[0].name,
            "name": " ".join(p.stem.split("_")[:-1]),
            "description": params.pop("help", "N/A"),
            "parameters": params,
        }
    except:
        notparsed.append(p)

line = ""
for p in notparsed:
    line += f"{str(p.parents[0].name)} {str(p.name)}\n"
Path("not-parsed.dat").write_text(line)

# pprint(DATA)
