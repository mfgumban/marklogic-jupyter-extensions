import json
import pandas
import shlex
import xmltodict
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from requests_toolbelt.multipart.decoder import MultipartDecoder
from IPython.core.magic import Magics, magics_class, line_magic, cell_magic, needs_local_scope

class ConnectNotDefinedError(Exception):
    pass

class InvalidArgsError(Exception):
    pass

class EvalError(Exception):
    pass

class CoercionError(Exception):
    pass

@magics_class
class MarkLogicMagics(Magics):
    def __init__(self, shell):
        super(MarkLogicMagics, self).__init__(shell)
        self.session = None
        self.session_baseurl = ""

    def _check_for_session(self):
        if self.session is None:
            raise ConnectNotDefinedError("No server connection defined.  Did you use '%marklogic_connect'?")

    def _check_invalid_args(self, args, valid_args):
        invalid_args = [arg for arg in args if arg not in valid_args]
        if len(invalid_args) != 0:
            raise InvalidArgsError("Invalid arguments " + ", ".join(invalid_args))

    def _eval_adhoc(self, lang, line, cell):
        self._check_for_session()

        valid_lang = ("xquery", "javascript")
        if lang not in valid_lang:
            raise TypeError("lang can only be " + ", ".join(valid_lang))
        
        args = shlex.split(line, comments = True)
        self._check_invalid_args(args, ("-raw", "-dataframe"))
        output_opt = "default"
        if "-raw" in args:
            output_opt = "raw"
        if "-dataframe" in args:
            output_opt = "dataframe"
        
        # execute code on MarkLogic
        url = self.session_baseurl + "/v1/eval"
        body = {
            lang: cell
        }
        output = []
        response = self.session.post(url, data = body)
        if response.status_code == 200:
            headers = { header.lower(): value for (header, value) in response.headers.items() } 
            # as per docs, /v1/eval should always return multipart/mixed
            if "content-type" in headers and headers["content-type"].startswith("multipart/mixed"):
                mp_data = MultipartDecoder.from_response(response)
                for part in mp_data.parts:
                    part_headers = { header.decode("utf-8").lower(): value.decode("utf-8") for (header, value) in part.headers.items() } 
                    part_content_type = part_headers["content-type"]
                    part_x_primitive = part_headers["x-primitive"]
                    part_content = part.content.decode("utf-8")
                    data = part_content if output_opt == "raw" else self._parse_content(part_content, part_content_type, part_x_primitive)
                    output.append(data)
        else:
            raise EvalError("Request to %s returned %s %s: %s" % (url, response.status_code, response.reason, response.text))

        output = output[0] if len(output) == 1 else output
        if output_opt == "dataframe":
            try:
                output = pandas.DataFrame(output) # try to fit into a dataframe, may raise an exception depending on result's shape
            except:
                raise CoercionError("Unable to fit response into a DataFrame")
        return {
            "status_code": response.status_code,
            "output": output,
            "output_opt": output_opt,
            "args": args
        }

    def _parse_content(self, content, content_type, x_primitive):
        output = ""
        ctype = content_type.lower()
        xprim = x_primitive.lower()
        if ctype == "application/json":
            output = json.loads(content)
        elif ctype in ("text/xml", "application/xml"):
            output = xmltodict.parse(content, dict_constructor = dict, process_namespaces = True)
        elif ctype == "text/plain":
            if xprim == "boolean":
                output = content.lower() in ("true", "1")
            elif xprim in ("decimal", "double", "float"):
                output = float(content)
            elif xprim == "integer":
                output = int(content)
            else:
                output = content
        return output

    @line_magic
    def marklogic_connect(self, line):
        all_args = iter(shlex.split(line, comments = True))
        url, args = next(all_args, None), list(all_args)
        self._check_invalid_args(args, ("-basic", "-digest"))

        rparts = requests.utils.urlparse(url)
        rparts_error_msg = " -- example url would be: http://username:password@localhost:8010"
        if rparts.scheme not in ("http", "https"):
            raise InvalidArgsError("Unable to determine scheme, please indicate http or https" + rparts_error_msg)
        if not rparts.hostname:
            raise InvalidArgsError("Unable to determine hostname" + rparts_error_msg)
        if not rparts.port:
            raise InvalidArgsError("Unable to determine port" + rparts_error_msg)
        if not rparts.username or not rparts.password:
            raise InvalidArgsError("Unable to determine username and/or password" + rparts_error_msg)
        is_auth_basic = "-basic" in args
        is_auth_digest = "-digest" in args
        if is_auth_basic and is_auth_digest:
            raise InvalidArgsError("-basic and -digest are mutually exclusive, please only use one")

        # default to digest if none specified
        auth = HTTPBasicAuth(rparts.username, rparts.password) if is_auth_basic else HTTPDigestAuth(rparts.username, rparts.password)
        self.session = requests.session()
        self.session.auth = auth
        self.session_baseurl = "%s://%s:%s" % (rparts.scheme, rparts.hostname, rparts.port)

        # test out the connection
        response = self._eval_adhoc("xquery", "", "()")
        if response["status_code"] == 200:
            print("Connection to %s OK" % (self.session_baseurl))

    @cell_magic
    def marklogic_xqy(self, line, cell):
       return self._eval_adhoc("xquery", line, cell)["output"]

    @cell_magic
    def marklogic_sjs(self, line, cell):
        return self._eval_adhoc("javascript", line, cell)["output"]

    @cell_magic
    def marklogic_sql(self, line, cell):
        sql = " ".join(cell.splitlines())
        sql = sql.replace("\"", "\\\"")
        script = "xdmp.sql(\"" + sql + "\", [\"map\"]);"
        argsline = "-dataframe" if not line.strip() else line # default to dataframe for SQL queries
        return self.marklogic_sjs(argsline, script)

    @line_magic
    @needs_local_scope
    def marklogic_doc_insert(self, line, local_ns = None):
        self._check_for_session()
        args = shlex.split(line, comments = True)
        arg_count = len(args)
        if arg_count != 1:
            raise InvalidArgsError("Invalid arguments, expected 1 but found " + str(arg_count))
        opts_name = args[0]
        if opts_name not in local_ns:
            raise InvalidArgsError("Cannot find variable %s in local scope" % (opts_name))
        opts = local_ns[opts_name]
        if not isinstance(opts, dict):
            raise InvalidArgsError("Variable %s must be a dict" % (opts_name))
        doc_uri = str(opts["uri"]) if "uri" in opts else None
        doc_content = opts["content"] if "content" in opts else None
        doc_format = str(opts["format"]).lower() if "format" in opts else None
        if not doc_uri:
            raise InvalidArgsError("%s doesn't specify the document uri, ensure there is dictionary entry for 'uri'" % (opts_name))
        if not doc_content:
            raise InvalidArgsError("%s doesn't specify the document content, ensure there is dictionary entry for 'content'" % (opts_name))
        mimetype = None
        if doc_format == "xml":
            mimetype = "application/xml"
        elif doc_format == "json":
            mimetype = "application/json"
        elif doc_format == "binary":
            mimetype = "application/octet-stream"

        # insert document
        qparams = { "uri": doc_uri }
        headers = { "content-type": mimetype } if mimetype else {}
        url = self.session_baseurl + "/v1/documents"
        response = self.session.put(url, headers = headers, params = qparams, data = doc_content)
        if response.status_code == 201 or response.status_code == 204:
            print("%s %s %s" % (response.status_code, response.reason, doc_uri))
        else:
            raise EvalError("Request to %s returned %s %s: %s" % (url, response.status_code, response.reason, response.text))

        
        

