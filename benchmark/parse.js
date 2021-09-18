/*
The regexp-tree library is very widely used (over 900,000 public GitHub projects use it).

This process is created from the main Python process, and listens to stdin expressions to
parse. The expressions are parsed and formatted, then printed into stdout as a standard
output object.

See details in benchmark/convert.py#FAdoize
*/
const regexp = require("regexp-tree")

/*
LISTEN AND RESPOND TO DATA INPUTS
*/
process.stdin.on("data", (data) => {
    data = data.toString()
    if (data.endsWith("\r\n")) data = data.substring(0, data.length - 2)
    else if (data.endsWith("\n")) data = data.substring(0, data.length - 1)

    const output = {
        logs: [],
        error: 0,
        formatted: 0
    }
    try {
        output.logs.push("Parsing expression /" + data + "/ ... ")

        let str = ""
        for (const c of data)
            if (c == "/")          str += "\\/"
            else if (c.length > 1) str += `\\u\{${c.codePointAt(0).toString(16)}}`
            else                   str += c

        const ast = regexp.parse("/" + str + "/u")
        const formatted = nodeToString(ast.body, output)
        output.formatted = formatted
    }
    catch (e) {
        output.error = e.stack
    }
    finally {
        console.log(JSON.stringify(output))
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
function nodeToString(node, output, chars=null) {
    // output.logs.push(`nodeToString: ${chars}\n${JSON.stringify(node)}`)

    switch (node.type) {
        case "Alternative":
            return buildConcatRecursively(node.expressions.map(x => nodeToString(x, output)))

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
            else { // non-meta character
                // character classes require different escapings than atoms
                const escapeScheme = (chars == null ? "rnt\\()[]+*?" : "rnt\\[]^-")
                return (escapeScheme.includes(node.symbol) ? "\\" : "") + node.symbol
            }

        case "CharacterClass":
            children = node.expressions.map((e) => nodeToString(e, output, node.negative ? true : false)).join("")
            if (children.length == 0)
                throw Error("Empty CharacterClass")

            return `[${node.negative ? "^" : ""}${children}]`

        case "ClassRange":
            return `${nodeToString(node.from, output)}-${nodeToString(node.to, output)}`

        case "Disjunction":
            return `(${nodeToString(node.left, output)} + ${nodeToString(node.right, output)})`

        case "Group":
            if ("expression" in node) // empty group "()"
                return nodeToString(node.expression)
            else
                return ""

        case "Repetition":
            const expression = nodeToString(node.expression, output)

            switch (node.quantifier.kind) {
                case "*":
                    return `${expression}*`
                case "+":
                    return `(${expression} ${expression}*)`
                case "?":
                    return `${expression}?`
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
                }, output)
            }

            if (from == to) // exactly from x's
                return xReps(from)
            else if (to == undefined) { // xx...x x* case
                const fromReps = xReps(from)
                if (fromReps.length == 0)
                    return `${expression}*`
                else
                    return `(${fromReps} ${expression}*)`
            }
            else { // exactly from x's followed by "some" more
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