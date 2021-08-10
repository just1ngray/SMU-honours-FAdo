/*
The regexp-tree library is very widely used (over 900,000 public GitHub projects use it).

This process is created from the main Python process, and listens to stdin expressions to
parse. The expressions are parsed and formatted, then printed into stdout. Finally, the
line "> Done0! <\n" is printed to stdout to signal the input expression has been finished.

See details in benchmark/util.py#FAdoize
*/
const regexp = require("regexp-tree")

/*
LISTEN AND RESPOND TO DATA INPUTS
*/
process.stdin.on("data", (data) => {
    data = data.toString()
    if (data.endsWith("\r\n")) data = data.substring(0, data.length - 2)
    else if (data.endsWith("\n")) data = data.substring(0, data.length - 1)

    try {
        console.log("Parsing expression /" + data + "/ ... ")

        let str = ""
        for (const c of data)
            if (c.length > 1) str += `\\u\{${c.codePointAt(0).toString(16)}}`
            else              str += c

        const ast = regexp.parse("/" + str + "/u")
        const formatted = nodeToString(ast.body)
        console.log(formatted)
    }
    catch (e) {
        console.log(e)
        console.log("ERROR ^^^^")
    }
    finally {
        console.log("> Done0! <")
    }
});

/**
 * Creates left-recursive concatenation with an array of tokens.
 * @param tokens the string tokens to left-recursively concatenate
 * @returns the FAdo-accepting string of the concatenation
 */
function buildConcatRecursively(tokens) {
    function f() {
        if (tokens.length == 1)
            return tokens[0]
        else if (tokens.length == 2)
            return `(${tokens[0]} ${tokens[1]})`
        else {
            const next = tokens.pop()
            return `(${f()} ${next})`
        }
    }
    return f()
}

/**
 * Convert a regexp-tree parsed AST into a formatted string
 * @param node the node of the tree to convert
 * @param chars null if not in char-class, true if in char-class, and false if the char-class
 *  is negated
 * @returns the formatted string
 */
function nodeToString(node, chars=null) {
    // console.log("nodeToString:", node, chars) // uncomment for debugging (performance penalty)

    switch (node.type) {
        case "Alternative":
            return buildConcatRecursively(node.expressions.map(nodeToString))

        case "Assertion":
            switch (node.kind) {
                case "^":
                    return "<ASTART>"
                case "$":
                    return "<AEND>"
                default:
                    throw new Error("Cannot handle assertion " + node.kind)
            }

        case "Backreference":
            throw new Error("Cannot handle backreference")

        case "Char":
            if (node.kind == "meta") { // meta-character
                if (node.value == ".")
                    return "@any"
                const encoded = node.value.substr(-1)
                const isUpper = encoded.toUpperCase() == encoded

                if (chars == null) // not inside character class
                    switch (encoded) {
                        case "s": return " "
                        case "S": return "[^ ]"
                        case "w": return "[0-9A-Za-z_]"
                        case "W": return "[^0-9A-Za-z_]"
                        case "d": return "[0-9]"
                        case "D": return "[^0-9]"
                    }
                else if (isUpper) // inside character class but negated (i.e., \D)
                    throw new Error("Unsupported negated character class in [...]")
                else
                    switch (encoded) {
                        case "s": return " "
                        case "w": return "0-9A-Za-z_"
                        case "d": return "0-9"
                    }
                return node.value
            }
            else {
                // allowed escape characters    v  ... the rest are understood without \ because non-ambiguous ()
                const escaped = node.escaped && "rnt".includes(node.symbol)
                return `${escaped ? "\\" : ""}${node.symbol}`
            }

        case "CharacterClass":
            children = node.expressions.map((e) => nodeToString(e, node.negative ? true : false)).join("")
            if (children.length == 0)
                throw Error("Empty CharacterClass")

            return `[${node.negative ? "^" : ""}${children}]`

        case "ClassRange":
            return `${nodeToString(node.from)}-${nodeToString(node.to)}`

        case "Disjunction":
            return `(${nodeToString(node.left)} + ${nodeToString(node.right)})`

        case "Group":
            return nodeToString(node.expression)

        case "Repetition":
            const expression = nodeToString(node.expression)

            switch (node.quantifier.kind) {
                case "*":
                    return `${expression}*`
                case "+":
                    return `(${expression} ${expression}*)`
                case "?":
                    return `(${expression})?`
            }
            // kind = "Range"
            let { from, to } = node.quantifier
            if (from == undefined) from = 0
            function xReps(x) {
                if (x == 0) return ""
                else if (x == 1) return expression
                else return nodeToString({
                    type: "Alternative",
                    expressions: new Array(x).fill(node.expression)
                })
            }

            if (from == to)
                return xReps(from)
            else if (to == undefined)
                return `(${xReps(from)} ${expression}*)`
            else {
                function xMore(x) {
                    let maxChosen = 0
                    let concat = []
                    for (let i = 1; i + maxChosen <= x; i *= 2) {
                        concat.push(`(@epsilon + ${xReps(i)})`)
                        maxChosen += i
                    }

                    if (x - maxChosen > 0)
                        for (const token of xMore(x - maxChosen))
                            concat.push(token)

                    return concat
                }
                if (from == 0)
                    return buildConcatRecursively(xMore(to - from))
                else
                    return `(${xReps(from)} ${buildConcatRecursively(xMore(to - from))})`
            }

        default:
            throw new Error("Unrecognized " + JSON.stringify(node))
    }
}