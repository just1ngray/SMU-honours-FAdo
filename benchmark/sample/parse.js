/*
The regexp-tree library is very widely used (over 900,000 public GitHub projects use it).

This is called within a python benchmark.sample.sample#Sampler instance. The expression to
parse is passed as a command-line argument.

Escaping notes:
    - \d* is passed as \d*
    - In languages like Java where the \ is inside a pair of double-quotes, the first \
        needs to be filtered out:
        Java expression: "\\d*" should be passed as \d*
    - If a double-quote appears inside the passed argument, they must be escaped.
*/
const regexp = require("regexp-tree")

function nodeToString(node, chars=null) {
    console.log("nodeToString:", node)

    switch (node.type) {
        case "Alternative":
            const tokens = node.expressions.map(nodeToString)
            function buildRecursively() {
                if (tokens.length <= 2) {
                    return `(${tokens[0]} ${tokens[1]})`
                }
                else {
                    const next = tokens.pop()
                    return `(${buildRecursively()} ${next})`
                }
            }

            return buildRecursively()

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
            else
                return `${node.escaped ? "\\" : ""}${String.fromCharCode(node.codePoint)}`

        case "CharacterClass":
            return `[${node.negative ? "^" : ""}${
                node.expressions.map((e) => nodeToString(e, node.negative)).join("")}]`

        case "ClassRange":
            if (node.from > node.to)
                throw new Error("Ill-formed ClassRange " + JSON.stringify(node))
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
                    let concat = ""
                    for (let i = 1; i + maxChosen <= x; i *= 2) {
                        concat += `(@epsilon + ${xReps(i)})`
                        maxChosen += i
                    }
                    return (x - maxChosen == 0) ? concat : `${concat} ${xMore(x - maxChosen)}`
                }
                return `(${xReps(from)} ${xMore(to - from)})`
            }

        default:
            console.error("Unrecognized", node)
            process.exit(1)
    }
}

if (process.argv.length > 3)
    throw new Error("Too many arguments provided in process.argv: "
        + JSON.stringify(process.argv, null, 2))

console.log("Parsing expression /" + process.argv[2] + "/ ... ")
const ast = regexp.parse("/" + process.argv[2] + "/")
console.log("OUTPUT:")
const formatted = nodeToString(ast.body)
console.log(formatted)