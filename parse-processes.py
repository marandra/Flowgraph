import os
from pathlib import Path
import ast
import json
from pprint import pprint


def create_process_node(path, descr, iparams, oparams):

    name = p.stem  # apply_inlet_process
    title = " ".join(name.split("_")).title()  # Apply Inlet Process
    fname = "".join(title.split())  # ApplyInletProcess
    group = path.parents[0].name
    if "KratosMultiphysics" in group:
        module = group
    else:
        module = f"{path.parents[1].name}.{group}"
    props = json.dumps(oparams, indent=4)
    fprops = "\n    ".join(props.split("\n"))

    # Write funtion definition
    lines = f'function {fname}() {{' + '\n'
    for mp in iparams:
        lines += f'    this.addInput("{mp}", "string");' + '\n'
    lines += '    this.addOutput("Process", "process");' + '\n'
    lines += f"    this.properties = '{fprops}';" + '\n'
    lines += '    this.size = this.computeSize();' + '\n'
    lines += '};' + '\n'
    lines += '\n'

    # Write "onExecute"
    lines += f'{fname}.prototype.onExecute = function() {{' + '\n'
    lines += '    output = {' + '\n'
    lines += f'        "python_module": "{name}",' + '\n'
    lines += f'        "kratos_module": "{module}"' + '\n'
    lines += '    }' + '\n'
    lines += '    output["Parameters"] = this.properties' + '\n'
    for i, mp in enumerate(iparams):
        lines += f'    output["Parameters"]["{mp}"] = this.getInputData({i})' + '\n'
    lines += '};' + '\n'
    lines += '\n'

    # Write title, description, registration, ...
    lines += f'{fname}.title = "{title}";' + '\n'
    lines += '\n'
    lines += f'{fname}.desc = "{descr}";' + '\n'
    lines += '\n'
    lines += f'LiteGraph.registerNodeType("PROCESSES/{group}/{title}", {fname});\n'

    return lines


def get_node_params(params):
    descr = params.pop("help", "N/A")
    ip = []
    op = {}
    for k, v in params.items():
        # heuristics for the processing of parameters
        # . remove obsolete params
        if "computing_model_part_name" in k:
            continue
        if "model_part" in k:
            ip.append(k)
        else:
            op[k] = v
    return descr, ip, op


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
    #print(f"Found init: {init_node.name}")
    varname = init_node.args.args[-1].arg
    #print(f"Found variable name: {varname}")

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


if __name__ == "__main__":
    BASE = [x for x in os.getenv("PYTHONPATH").split(":") if "Kratos/bin" in x][0]
    PATHS = (Path(BASE) / "KratosMultiphysics").glob("**/*_process.py")

    notparsed = []
    parsed = []
    for p in PATHS:

        # Files to skip
        if "python_process.py" in p.name:
            continue

        #DEBUG:
        if "boussinesq" not in p.name:
            #continue
            pass

        code = p.read_text()
        try:
            params = json.loads(get_default_params_from_process(p.read_text()))
            if not params:
                notparsed.append(p)
                print(f"NOT PARSED: {p.parents[0].name} {p.name}")
                continue
            descr, i_params, o_params = get_node_params(params)

            # DEBUG
            if len(o_params) == 0:
                print("DEBUG:")
                pprint(get_default_params_from_process(p.read_text()))
                stop

            node_code = create_process_node(p, descr, i_params, o_params)
            opath = Path(f"js/nodes/PROCESSES/{p.parents[0].name}")
            opath.mkdir(parents=True, exist_ok=True)
            ppath = opath/f"{p.stem}.js"
            ppath.write_text(node_code)
            parsed.append(str(ppath))


        # DEBUG
        except(AttributeError, IndexError):
            notparsed.append(p)
            print(f"NOT PARSED except: {p.parents[0].name} {p.name}")

    # update index.html with parsed processes
    lines = "\n        <!-- Processes nodes -->\n"
    for p in parsed:
        lines += f'        <script type="text/javascript" src="{p}"></script>\n'
    print(lines)

    # write file with not-parsed processes
    line = ""
    for p in notparsed:
        line += f"{str(p.parents[0].name)} {str(p.name)}\n"
    Path("not-parsed.dat").write_text(line)
