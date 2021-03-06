#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
import lark

from lark import Lark, Transformer


class TsToJson(Transformer):
    def comment(self, elements):
        return {"description": str("\n".join([x.strip() for x in elements[0].replace("*", "").replace("/", "").split("\n") if x != ""]))}

    def tstype(self, elements):
        ret_val = []
        ret_dict = {}

        for element in elements:
            if type(element) == lark.lexer.Token and element.type == "CNAME":
                ret_val.append(str(element))
            elif type(element) == lark.tree.Tree and element.data == "conjunction":
                cs = [str(child) for child in element.children]
                ret_val.append({"conjunction": cs})
            elif type(element) == lark.tree.Tree:
                ret_val[-1] = ret_val[-1] + "[]"
            elif type(element) == dict:
                ret_dict.update(element)
            else:
                ret_val.append(str(element))

        if len(ret_val) == 0:
            return {"type": ret_dict}
        else:
            return {"type": ret_val}

    def optional(self, elements):
        return {"optional": True}

    def function(self, elements):
        params = {}

        i = 0
        while i < len(elements):
            params[str(elements[i])] = elements[i + 1]
            i += 2

        return {"params": params}

    def identifier(self, elements):
        if len(elements) > 0 and type(elements[0]) == dict and "params" in elements[0]:
            return {"name": "anonymous_function", "params": elements[0]["params"]}
        if len(elements) > 1 and type(elements[1]) == dict and "params" in elements[1]:
            return {"name": str(elements[0]), "params": elements[1]["params"]}
        elif len(elements) == 1:
            return str(elements[0])

        return {"indexed": True, "name": str(elements[0]), "type": elements[1]}

    def typedef(self, elements):
        ret_dict = {}

        name = None

        for element in elements:
            if type(element) == dict and "description" in element:
                ret_dict["description"] = element["description"]
            elif type(element) == dict and "params" in element:
                ret_dict["function"] = True
                ret_dict["parameters"] = element["params"]
                name = element["name"]
            elif type(element) == dict and "indexed" in element:
                ret_dict["indexed"] = element["type"]
                name = element["name"]
            elif type(element) == dict and "type" in element:
                ret_dict["type"] = element["type"]
            elif type(element) == dict and "optional" in element:
                ret_dict["optional"] = True
            elif type(element) == lark.tree.Tree and element.data == "const":
                ret_dict["constant"] = True
            elif type(element) == lark.tree.Tree and element.data == "readonly":
                ret_dict["readonly"] = True
            elif type(element) == lark.tree.Tree and element.data == "inline_comment":
                ret_dict["description"] = str(element.children[0])
            elif type(element) == str:
                name = str(element)

        if name is None:
            raise Exception("Has no name")

        return {name: ret_dict}

    def int(self, elements):
        elements = [i for i in elements if not str(i) == "export" and not str(i) == "interface"]

        descr = None
        name = None
        extends = None
        start_index = 1

        if type(elements[0]) == dict and "description" in elements[0]:
            descr = elements[0]["description"]
            name = str(elements[1])
            start_index = 2
        elif type(elements[1]) == lark.tree.Tree and elements[1].data == "extends":
            name = str(elements[0])
            extends = [str(i) for i in elements[1].children]
            start_index = 2
        else:
            name = str(elements[0])

        if name is None:
            raise Exception("Has no name")

        ret_val = {name: {}}

        if descr is not None:
            ret_val[name]["description"] = descr

        if extends is not None:
            ret_val[name]["extends"] = extends

        for i in range(start_index, len(elements)):
            ret_val[name].update(elements[i])

        return ret_val


tsParser = Lark(r"""
    int: comment? EXPORT? INTERFACE CNAME extends? "{" typedef* "}"

    typedef : comment? prefix? identifier optional? ":" tstype (";" | ",")? inline_comment?

    identifier : CNAME function?
            | "[" CNAME ":" tstype "]"
            | function

    function : "(" CNAME ":" tstype ("," CNAME ":" tstype)* ")"

    prefix : "const" -> const
            | "readonly" -> readonly

    extends : "extends" CNAME ("," CNAME)*

    optional : "?"

    comment: /\/\*((.|\s)*?)\*\//

    inline_comment: /\/\/.*\n/

    tstype : (CNAME | ESCAPED_STRING | OTHER_ESCAPED_STRINGS | "{" typedef* "}" | conjunction) isarray? ("|" (CNAME | ESCAPED_STRING | OTHER_ESCAPED_STRINGS | "{" typedef* "}" | conjunction )isarray?)*

    isarray : "[]"

    conjunction : "(" CNAME ( "&" CNAME)* ")"

    INTERFACE: "interface"
    EXPORT: "export"

    OTHER_ESCAPED_STRINGS : "'" _STRING_ESC_INNER "'"

    %import common.CNAME
    %import common.WS
    %import common.NEWLINE
    %import common.ESCAPED_STRING
    %import common._STRING_ESC_INNER
    %ignore WS
    %ignore NEWLINE
    """, start='int')


def transform(interface_data, debug=False):
    tree = tsParser.parse(interface_data)

    if debug:
        print(tree.pretty())

    return json.dumps(TsToJson().transform(tree), indent=4, sort_keys=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Typescript Interface Parser")
    parser.add_argument('file', metavar='file', type=str, help='The path to the file that ONLY contains the typescript interface')
    parser.add_argument('-p', '--parse_tree', action='store_true', help="Pretty print the parse tree")
    parser.add_argument('-o', '--output', default=False, help="Write the json to an output file")

    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print("File {} does not exists".format(args.file))
        sys.exit(0)

    content = None

    with open(args.file, "r") as var:
        content = var.read()

    if content is None:
        print("File is empty")
        sys.exit(0)

    formatted_output = transform(content, args.parse_tree)

    if not args.output:
        print(formatted_output)
    else:
        with open(args.output, "w") as var:
            var.write(formatted_output)
