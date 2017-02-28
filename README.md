# Lispy - A LISP Interpreter Written in Python
There are many reasons why you would want to write an interpreter, even more so if you
enjoyed your courses in compilers and programming languages semantics, like I did.
Why LISP? Because its syntax is very simple, so you don't have to waste time in
coding boring parts such as lexing and parsing, and you can jump straight in the fun
pars: interpreting!

## Example
```
(def readme
    (let (lines ((. readlines (open "README.md"))))
        (map (# (. strip %0)) lines)))

(def headers
    (filter (# and %0 (= (first %0) "#")) readme))

(def header_titles
    (map (# let (words ((. split %0) " "))
            (+ "\t- " ((. join " ") (rest words))))
        headers))

(print "Sections of the readme:\n" ((. join "\n") header_titles))

(comment - almost forgot...)
(pyimport this antigravity)
```


## Main Feature

### REPL
Based on [python-prompt-toolkit](https://github.com/jonathanslenders/python-prompt-toolkit);
it still needs some love, but has the basics. Use `ctrl+enter` to evaluate an
input, as `enter` inserts a new line:

```
$ python repl.py -S
>>> (+ 1 1)
2
```

### Python interoperability
Thanks to `pyimport` and `pyimport_from`, it is possible to import python
objects and use them:

```
>>> (pyimport_from sklearn.svm SVC)
... (pyimport_from sklearn datasets)
... (pyimport_from sklearn.model_selection train_test_split)
...
... (let (iris ((. load_iris datasets))
...         X (. data iris) y (. target iris)
...         clf (SVC))
...     (do
...         ((. fit clf) X y)
...         (print "Training accuracy: " ((. score clf) X y))))
Training accuracy:  0.986666666667
None
```

### Stack Traces
When exceptions happen, the stacktrace of the interpreted code is printed, together
with a python stacktrace of the interpreter (not shown here)

```
>>> (defn stupid_divide (x)
...     (if (= x 0)
...         (/ 100 x)
...         (let (y (stupid_divide (dec x)))
...             (/ x y))))
... (stupid_divide 3)
Call Stack (most recent last):
  (stupid_divide x=3)
  (if (= x 0) (/ 100 x) (let (...) (...)))
  (let (y (...)) (/ x y))
  (stupid_divide x=2)
  (if (= x 0) (/ 100 x) (let (...) (...)))
  (let (y (...)) (/ x y))
  (stupid_divide x=1)
  (if (= x 0) (/ 100 x) (let (...) (...)))
  (let (y (...)) (/ x y))
  (stupid_divide x=0)
  (if (= x 0) (/ 100 x) (let (...) (...)))
Exception happened here: (/ 100 x)
```

### Standard library
It's still tiny, but it's there (`lispy/stdlib.lispy`)! I tried to implement as few
utilities as possible with python (`lispy/globals.py`), and leave the rest as
testing playground for the interpreter. Beware: I tried to write it in functional
style, but I'm not a good functional programmer, and I focused on "clarity"
(hopefully) rather than efficiency, so... Yea :)


## Structure
The juicy part is in `interpreter.py`. There are two implementations: a recursive
version and an iterative version. The recursive version is quite natural to
write and understand, given the recursive structure of LISP code; on the other hand,
it takes very little to kill the interpreter with a `StackOverflowException` (around 
70/80 recursive calls). For this reason, it is not maintained anymore, but preserved
as an illustrative example.

To "solve" the recursion limit issue, there is an iterative interpreter, which
basically maintains a stack of coroutines and moves parameters and return values
around (it's recursion disguised!). It's pretty fun, if you ask me: when you are
evaluating an expression, and need to evaluate  a sub-expression (e.g. when
evaluating an `if`, you need to evaluate the condition), simply `yield` it, and
you will magically receive its value back; the last thing you should yield is the
final value of the expression, or an expression to evaluate in its place.
For example, this is how `(if cond iftrue iffalse)` is evaluated:


```
def handle_if(self, ctx, expr, cond, iftrue, iffalse):
    cval = yield cond, ctx
    if cval:
        yield iftrue, ctx
    else:
        yield iffalse, ctx
```

Note that `cond`, `iftrue` and `iffalse` are expression trees, while `cval` is the
evaluated value of `cond` (e.g. if `cond` is `(= 1 0)` then `cval` will be python's
`False`). Finally, the interpreter will evaluate either `iftrue` of `iffalse` to get
the value of the condition.

In case you are wondering, `ctx` is a variable that holds the execution context in
which the expression is evaluated; in other words, it is a kind of dictionary that
contains the variables visible at that point. Contexts can have a parent context,
and may "override" the values of its variables, so that only the youngest version is
visible. The root context contains language builtins that can be accessed and
redefined from everywhere; currently, the builtins are implemented in python and
contained in `globals.py`.

Functions are implemented as a class that is initialized with the body of the
function and the formal parameters, and, when called, creates a new context with
the actual parameters and evaluates the body. Basically, any python callable can
be used as a function from the LISP code! This made integrating python into Lispy
straightforward, and relieves me from the burden of implementing lists and
dicts myself (which would entail nuking the tokenization/parsing modules), as well
as anything else that is found in the python ecosystem!

## Roadmap
Things I would like to implement, sooner or later:
 - Macros (I need to understand them myself, first)
 - A decent REPL
 - A real parser

## Syntax
This is what is currently supported, and how to do it.

#### Conditionals
`(if <condition> <iftrue> <iffalse>)`

If condition evaluates to true then iftrue is evaluated and returned, otherwise
iffalse is evaluated and returned.

#### Function Definition

`(defn <name> (arg-1 ... arg-n [& vararg]) <body>)`

Introduces a new function. The last argument can be a vararg.

#### Anonymous Function Definityion
`(# <expr-1> ... <expr-n>)`

Introduces a new function with no name (unless you give it one!), which thus can
only be called; arguments can be accessed via `%i`, where `i` is the i-th
argument (e.g. `%1` is the *second* argument). It is equivalent to
`(defn _ (%0 ... %m) (<expr-1> ... <expr-n>))`, note the parentheses surrounding
the wrapped expressions.

#### Function Invokation
`(<function> <arg-1> ... <arg-n> [& <vararg>])`

Evaluates to the value returned by the function called with the given parameters.
The last argument can be a vararg. `<function>` can be a name or an expression
that evaluates to a function (e.g. an anonymous function).

#### Let Expression
`(let (name-1 <expr-1> ... name-n <expr-n>) <expr>)`

Introduces new definitions in the context and evaluates `expr`, whose value is
the value of the whole let expression. The definitions are discarded afterwards
(i.e. outside this block).

#### Name Definition
`(def name-1 <expr-1> ... name-n <expr-n>)`

Introduces new definitions in the context. The value of the expression is the
value of `expr-n`.

#### Do blocks
`(do expr-1 ... expr-n)`

Evaluates all expressions in order, and returns the value of the last one. If an
expression has side effects, they will be visible afterwards (e.g. functions
defined in a do will be visible outside it).

#### Python Imports
 - `(pyimport mod-1 ... mod-n)`

   Imports the given python modules.

 - `(pyimport_from mod name)`

   Equivalent to `from mod import name`, note that `mod` can contain dots.

#### Property Invokation
`(. object property)`

Returns the property of the given object.

#### Comments
`(comment <text>)`

Ignores the content.
