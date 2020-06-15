# MarkLogic Jupyter Extensions

This IPython extension makes it easier to interact with [MarkLogic](http://marklogic.com) directly from your Jupyter notebooks by providing several _magic_ functions.

> *NOTE:* the extension is still a prototype, and is not currently published (via `pip`), but will be soon.  Feedback is definitely welcome!

## Trying it out

An example notebook is available to quickly check out the extension in action.  To run the example, you'll need the following installed:

- [Docker Desktop](https://www.docker.com/products/docker-desktop)
- [Gradle](http://gradle.org)

Steps to run the example:

- In the project directory, run `docker-compose up -d`.  This will setup a MarkLogic server and Jupyter server.
- Go to `http://localhost:8001` to initialize the MarkLogic server.  Follow the setup steps.  When asked, set the admin password to `admin`.
- Once MarkLogic is setup, run `./gradlew mlDeploy`.
- Run `./gradlew loadSampleData`.
- Go to `http://localhost:9999` to access Jupyter, use `admin` as the token/password.
- Click on the `work` folder and open the `example.ipynb` notebook.
- Open the `Cell` menu and click `Run All`.

## Using it on your own notebooks

You can use the extension in your own notebooks by copying the `marklogic_ext` directory in the same directory where your notebooks are located.  Remember to restart the kernel if your notebook(s) are already open.  This is a temporary process until the extension is published.

The extension uses _magic_ functions to extend or change the behavior of notebook cells, allowing you to interact with a MarkLogic server in different ways.  Magic functions are prefixed by `%` or `%%`.

### Initialization

Add these to a notebook cell to load the extension and connect to a MarkLogic server:

```python
%load_ext marklogic_ext
%marklogic_connect http://username:password@hostname:port
```

The extension uses digest authentication by default.  If you need to use basic authentication, add the `-basic` option:

```python
%marklogic_connect http://username:password@hostname:port -basic
```

If the server uses SSL, specify `https`:

```python
%marklogic_connect https://username:password@hostname:port
```

### Running server-side scripts

Run XQuery code directly in a cell:

```
%%marklogic_xqy

fn:collection("sample-data")
```

Run server-side Javascript directly in a cell:

```
%%marklogic_sjs

fn.collection("sample-data");
```

By default, the extension will try to coerce the script's output into corresponding Python types, such as numbers.  If the script returns XML, JSON objects, or JSON arrays, the extension will try to coerce them into Python dicts.  

You can use the `-dataframe` option to *try* coercing the output into a `pandas.DataFrame` object (or raise an error if it can't).  It is best to construct the DataFrame using an array of dicts, so it is recommended the script return an array or sequence of JSON or XML nodes.

```
%%marklogic_sjs -dataframe

return [{ id: 1, value: 3 }, { id: 2, value: 2 }, { id: 3, value: 1}];
```

There is also a `-raw` option that returns the output as an array of strings, regardless of their type.

### Running SQL queries

You can run SQL queries against your SQL views or TDEs:

```
%%marklogic_sql

SELECT * FROM schema.view LIMIT 50
```

SQL queries return `pandas.DataFrame` objects by default.  The `-raw` option is also available.

### Inserting Documents

You can insert documents directly from a cell:

```
insert_model = {
    "uri": "/models/example.onnx",
    "format": "binary",
    "content": onnx.SerializeToString()
}
%marklogic_doc_insert insert_model
```

In a Python cell, construct a dict variable with the document's `uri` and `content`.  The content can be a string or bytes.  By default, MarkLogic will try to decipher the document's mime type.  Optionally, you can explicitly specify the document type using `format` (can be `xml`, `json`, or `binary`).  Provide the variable as an argument to `%marklogic_doc_insert`.

