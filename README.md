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
        (map (defn _ (line) ((. strip line))) lines)))

(def headers
    (filter (defn _ (line)
            (and line (= (first line) "#")))
        readme))

(def header_titles
    (map (defn _ (hdr)
            (let (words ((. split hdr) " "))
                (+ "\t- " ((. join " ") (rest words)))))
        headers))

(print "Sections of the readme:\n" ((. join "\n") header_titles))

(comment -  almost forgot...)
(pyimport this antigravity)
```

## Structure
The juicy part is in `interpreter.py`. There are two implementations: a recursive
version and an iterative version. The recursive version is quite natural to
write and understand, given the recursive structure of LISP code; on the other hand,
it takes very little to kill the interpreter with a `StackOverflowException` (around 
70/80 recursive calls). To "solve" this, there is an iterative interpreter, which
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

#### Function Definition
(defn \<name\> (arg-1 ... arg-n [& vararg]) \<body\>)

introduces a new function. The last argument can be a vararg.

#### Function Invokation
(\<function\> \<arg-1\> ... \<arg-n\> [& \<vararg\>])

Evaluates to the value returned by the function called with the given parameters.
The last argument can be a vararg.

#### Let blocks
(let (name-1 \<expr-1\> ... name-n \<expr-n\>) \<expression\>)

Introduces new definitions in the context and evaluates the expression. The
definitions are discarded afterwards (i.e. outside this block).

#### Name Definition
(def name-1 \<expr-1\> ... name-n \<expr-n\>)

Introduces new definitions in the context. The value of the expression is the
value of `expr-n`.

#### Do blocks
(do expr-1 ... expr-n)

Evaluates all expressions in order, and returns the value of the last one. If an
expression has side effects, they will be visible afterwards (e.g. functions
defined in a do will be visible outside it).

#### Conditionals
(if \<condition\> \<iftrue\> \<iffalse\>)

If condition evaluates to true then iftrue is evaluated and returned, otherwise
iffalse is evaluated and returned.

#### Python Imports
(pyimport mod-1 ... mod-n)

Imports the given python modules.

#### Property Invokation
(. object property)

Returns the property of the given object.

#### Comments
(comment <text>)

Ignores the content.
