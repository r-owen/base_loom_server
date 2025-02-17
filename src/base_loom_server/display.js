// value is replaced by python code
const TranslationDict = { translation_dict }

// value is replaced by python code
const EnableSoftwareWeaveDirection = { enable_software_weave_direction }
console.log("EnableSoftwareWeaveDirection", EnableSoftwareWeaveDirection)

const MaxFiles = 10

const MinBlockSize = 11
const MaxBlockSize = 41

// Display gap on left and right edges end numbers
const EndDisplayGap = 3

// Display gap on left and right edges of warp and top and bottom edges of weft
const ThreadDisplayGap = 1

const ThreadHalfWidth = 5

const EndFont = "18px Times New Roman"

// Keys are the possible values of the LoomConnectionState.state messages
// Values are entries in ConnectionStateEnum
const ConnectionStateTranslationDict = {
    0: "disconnected",
    1: "connected",
    2: "connecting",
    3: "disconnecting",
}

const ModeEnum = {
    "WEAVING": 1,
    "THREADING": 2,
}

const SeverityColors = {
    1: "#ffffff",
    2: "yellow",
    3: "red",
}

const ShaftStateTranslationDict = {
    0: "?",
    1: "done",
    2: "moving",
    3: "error",
}

var ConnectionStateEnum = {}
for (var key of Object.keys(ConnectionStateTranslationDict)) {
    var name = ConnectionStateTranslationDict[key]
    ConnectionStateEnum[name] = name
}
Object.freeze(ConnectionStateEnum)

const numericCollator = new Intl.Collator(undefined, { numeric: true })

function t(phrase) {
    if (!(phrase in TranslationDict)) {
        console.log("Missing translation key:", phrase)
        return phrase
    }
    return TranslationDict[phrase]
}

/*
A minimal weaving pattern, including display code.

Javascript version of the python class of the same name,
with the same attributes but different methods.

Parameters
----------
datadict : dict object
    Data from a Python ReducedPattern dataclass.
*/
class ReducedPattern {
    constructor(datadict) {
        this.name = datadict.name
        this.color_table = datadict.color_table
        this.warp_colors = datadict.warp_colors
        this.threading = datadict.threading
        this.picks = []
        this.pick_number = datadict.pick_number
        this.pick_repeat_number = datadict.pick_repeat_number
        this.end_number0 = datadict.end_number0
        this.end_number1 = datadict.end_number1
        this.repeat_end_number = datadict.repeat_end_number
        for (var pickdata of datadict.picks) {
            this.picks.push(new Pick(pickdata))
        }
        this.warpGradients = {}
    }
}

/*
Data for a pick
*/
class Pick {
    constructor(datadict) {
        this.color = datadict.color
        this.shaft_word = BigInt(datadict.shaft_word)
    }
}


/*
Compare the names of two Files, taking numbers into account.

To sort file names in a FileList you must first 
convert the FileList to an Array::

    // myFileList is a FileList (which cannot be sorted)
    fileArr = Array.from(myFileList)
    fileArr.sort(compareFiles)
*/
function compareFiles(a, b) {
    // 
    return numericCollator.compare(a.name, b.name)
}

/*
This version does not work, because "this" is the wrong thing in callbacks.
But it could probably be easily made to work by adding a
"addEventListener method that takes an id, an event name, and a function
and uses "bind" in the appropriate fashion.

The result might be a nice -- each assignment would be a single line.
*/

class LoomClient {
    constructor() {
        this.ws = new WebSocket("ws")
        this.currentPattern = null
        this.weaveForward = true
        this.loomConnectionState = ConnectionStateEnum.disconnected
        this.loomConnectionStateReason = ""
        this.statusMessage = null
        this.jumpPickNumber = null
        this.jumpPickRepeatNumber = null
        this.threadGroupSize = 4
        this.threadLowToHigh = true

        // this.init()
    }

    init() {
        this.ws.onmessage = this.handleServerReply.bind(this)
        this.ws.onclose = handleWebsocketClosed

        // Assign event handlers for file drag-and-drop
        const dropAreaElt = document.body;

        ["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
            dropAreaElt.addEventListener(eventName, preventDefaults)
        });

        ["dragenter", "dragover"].forEach(eventName => {
            dropAreaElt.addEventListener(eventName, highlight)
        });

        ["dragleave", "drop"].forEach(eventName => {
            dropAreaElt.addEventListener(eventName, unhighlight)
        })

        function highlight(event) {
            dropAreaElt.style.backgroundColor = "#E6E6FA"
        }

        function unhighlight(event) {
            dropAreaElt.style.backgroundColor = "#FFFFFF"
        }

        dropAreaElt.addEventListener("drop", this.handleDrop.bind(this))

        var tabWeavingElt = document.getElementById("mode_weaving")
        tabWeavingElt.addEventListener("click", this.handleMode.bind(this, ModeEnum.WEAVING))

        var tabThreadingElt = document.getElementById("mode_threading")
        tabThreadingElt.addEventListener("click", this.handleMode.bind(this, ModeEnum.THREADING))

        var fileInputElt = document.getElementById("file_input")
        fileInputElt.addEventListener("change", this.handleFileInput.bind(this))

        var groupSizeElt = document.getElementById("thread_group_size")
        groupSizeElt.addEventListener("change", this.handleThreadGroupSize.bind(this))

        var jumpToEndForm = document.getElementById("jump_to_end_form")
        jumpToEndForm.addEventListener("submit", this.handleJumpToEndSubmit.bind(this))

        var jumpToEndResetElt = document.getElementById("jump_to_end_reset")
        jumpToEndResetElt.addEventListener("click", this.handleJumpToEndReset.bind(this))

        var jumpToPickForm = document.getElementById("jump_to_pick_form")
        jumpToPickForm.addEventListener("submit", this.handleJumpToPickSubmit.bind(this))

        var jumpToPickResetElt = document.getElementById("jump_to_pick_reset")
        jumpToPickResetElt.addEventListener("click", this.handleJumpToPickReset.bind(this))

        var jumpEndNumber0Elt = document.getElementById("jump_end_number0")
        // Select all text on focus, to make it easier to try different jump values
        // (without this, you are likely to append digits, which is rarely what you want)
        jumpEndNumber0Elt.addEventListener(`focus`, () => jumpEndNumber0Elt.select())
        jumpEndNumber0Elt.addEventListener("input", this.handleJumpToEndInput.bind(this))

        var jumpEndRepeatNumberElt = document.getElementById("jump_end_repeat_number")
        jumpEndRepeatNumberElt.addEventListener(`focus`, () => jumpEndRepeatNumberElt.select())
        jumpEndRepeatNumberElt.addEventListener("input", this.handleJumpToEndInput.bind(this))

        var jumpPickNumberElt = document.getElementById("jump_pick_number")
        jumpPickNumberElt.addEventListener(`focus`, () => jumpPickNumberElt.select())
        jumpPickNumberElt.addEventListener("input", this.handleJumpToPickInput.bind(this))

        var jumpPickRepeatNumberElt = document.getElementById("jump_pick_repeat_number")
        jumpPickRepeatNumberElt.addEventListener(`focus`, () => jumpPickRepeatNumberElt.select())
        jumpPickRepeatNumberElt.addEventListener("input", this.handleJumpToPickInput.bind(this))

        var oobChangeDirectionButton = document.getElementById("oob_change_direction")
        oobChangeDirectionButton.addEventListener("click", this.handleOOBChangeDirection.bind(this))

        var oobCloseConnectionButton = document.getElementById("oob_close_connection")
        oobCloseConnectionButton.addEventListener("click", this.handleOOBCloseConnection.bind(this))

        var oobNextPickButton = document.getElementById("oob_next_pick")
        oobNextPickButton.addEventListener("click", this.handleOOBNextPick.bind(this))

        var threadDirectionElt = document.getElementById("thread_direction")
        threadDirectionElt.addEventListener("click", this.handleToggleThreadDirection.bind(this))

        var weaveDirectionElt = document.getElementById("weave_direction")
        if (EnableSoftwareWeaveDirection) {
            weaveDirectionElt.addEventListener("click", this.handleToggleWeaveDirection.bind(this))
        } else {
            weaveDirectionElt.disabled = true
        }
        var patternMenu = document.getElementById("pattern_menu")
        patternMenu.addEventListener("change", this.handlePatternMenu.bind(this))
    }

    /*
    Process a reply from the loom server (data read from the web socket)
    */
    handleServerReply(event) {
        var messageElt = document.getElementById("read_message")
        if (event.data.length <= 80) {
            messageElt.textContent = event.data
        } else {
            messageElt.textContent = event.data.substring(0, 80) + "..."
        }
        var commandProblemElt = document.getElementById("command_problem")

        const datadict = JSON.parse(event.data)
        var resetCommandProblemMessage = true
        if (datadict.type == "CurrentEndNumber") {
            if (!this.currentPattern) {
                console.log("Ignoring CurrentEndNumber: no pattern loaded")
            }
            this.currentPattern.end_number0 = datadict.end_number0
            this.currentPattern.end_number1 = datadict.end_number1
            this.currentPattern.end_repeat_number = datadict.end_repeat_number
            this.displayThreadingPattern()
            this.displayEnds()
        } else if (datadict.type == "CurrentPickNumber") {
            if (!this.currentPattern) {
                console.log("Ignoring CurrentPickNumber: no pattern loaded")
            }
            this.currentPattern.pick_number = datadict.pick_number
            this.currentPattern.pick_repeat_number = datadict.pick_repeat_number
            this.displayWeavingPattern()
            this.displayPick()
        } else if (datadict.type == "Mode") {
            this.mode = datadict.mode
            this.displayMode()
        } else if (datadict.type == "ThreadDirection") {
            this.threadLowToHigh = datadict.low_to_high
            this.displayThreadingPattern()
            this.displayThreadDirection()
        } else if (datadict.type == "ThreadGroupSize") {
            this.threadGroupSize = datadict.group_size
            var threadGroupSizeMenu = document.getElementById("thread_group_size")
            threadGroupSizeMenu.value = this.threadGroupSize
        } else if (datadict.type == "JumpEndNumber") {
            this.jumpEndNumber0 = datadict.end_number0
            this.jumpEndRepeatNumber = datadict.repeatNumber
            this.displayJumpEnd()
        } else if (datadict.type == "JumpPickNumber") {
            this.jumpPickNumber = datadict.pick_number
            this.jumpPickRepeatNumber = datadict.pick_repeat_number
            this.displayJumpPick()
        } else if (datadict.type == "LoomConnectionState") {
            this.loomConnectionState = datadict
            this.loomConnectionState.state = ConnectionStateTranslationDict[datadict.state]
            this.displayStatusMessage()
        } else if (datadict.type == "ShaftState") {
            this.displayShaftState(datadict)
        } else if (datadict.type == "StatusMessage") {
            resetCommandProblemMessage = false
            this.statusMessage = datadict
            this.displayStatusMessage()
        } else if (datadict.type == "ReducedPattern") {
            this.currentPattern = new ReducedPattern(datadict)
            this.displayWeavingPattern()
            this.displayThreadingPattern()
            var patternMenu = document.getElementById("pattern_menu")
            patternMenu.value = this.currentPattern.name
        } else if (datadict.type == "PatternNames") {
            /*
            Why this code is so odd:
            • The <hr> separator is not part of option list, and there is no good way
              to add a separator in javascript, so I preserve the old one.
            • The obvious solution is to remove the old names, then insert new ones.
              Unfortunately that loses the <hr> separator.
            • So I insert the new names, then remove the old ones. Ugly, but at least
              on macOS Safari 18.1.1 this preserves the separator. If the separator
              is lost on other systems, the menu is still usable.
     
            Also there is subtlety in the case that there is no current weavingPattern
            (in which case the menu should be shown as blank).
            I wanted to avoid the hassle of adding a blank option now,
            which would then have to be purged on the next call to select_pattern.
            Fortunately not bothring to add a blank entry works perfectly!
            At the end the menu value is set to "", which shows as blank,
            and there is no blank option that has to be purged later.
            */
            var patternMenu = document.getElementById("pattern_menu")
            var patternNames = datadict.names
            var menuOptions = patternMenu.options
            var currentName = this.currentPattern ? this.currentPattern.name : ""

            // This preserves the separator if called with no names
            if (patternNames.length == 0) {
                patternNames.push("")
            }

            // Save this value for later deletion of old pattern names
            var numOldPatternNames = patternMenu.options.length - 1

            // Insert new pattern names
            for (var patternName of patternNames) {
                var option = new Option(patternName)
                menuOptions.add(option, 0)
            }

            // Purge old pattern names
            for (var i = 0; i < numOldPatternNames; i++) {
                menuOptions.remove(patternNames.length)
            }
            patternMenu.value = currentName
        } else if (datadict.type == "CommandProblem") {
            resetCommandProblemMessage = false
            var color = SeverityColors[datadict.severity]
            if (color == null) {
                color = "#ffffff"
            }
            commandProblemElt.textContent = datadict.message
            commandProblemElt.style.color = color
        } else if (datadict.type == "WeaveDirection") {
            this.weaveForward = datadict.forward
            this.displayWeaveDirection()
        } else {
            console.log("Unknown message type", datadict.type)
        }
        if (resetCommandProblemMessage) {
            commandProblemElt.textContent = ""
            commandProblemElt.style.color = "#ffffff"
        }
    }

    isConnected() {
        return this.loomConnectionState.state == ConnectionStateEnum.connected
    }

    /*
    Display ShaftState
    */
    displayShaftState(datadict) {
        var text = ""
        var textColor = "black"
        if (datadict.state == 1) {
            // Move is done; display shaft numbers
            var raisedShaftList = []
            var bitmask = BigInt(datadict.shaft_word)
            var shaft_number = 1

            while (bitmask !== 0n) {
                if (bitmask & 1n) {
                    raisedShaftList.push(shaft_number)
                }
                bitmask >>= 1n
                shaft_number++
            }
            text = raisedShaftList.join(", ")
        } else {
            text = t(ShaftStateTranslationDict[datadict.state])
            if (datadict.state == 3) {
                textColor = "red"
            }
        }
        var shaftStateElt = document.getElementById("shaft_state")
        shaftStateElt.textContent = text
        shaftStateElt.style.color = textColor
    }

    /*
    Display the status message (a combination of self.loomConnectionState and self.statusMessage)
    */
    displayStatusMessage() {
        var text = t(this.loomConnectionState.state)
        var textColor = "black"
        if (this.isConnected() && (this.statusMessage != null)) {
            text = this.statusMessage.message
            textColor = SeverityColors[datadict.severity]
        } else if (!this.isConnected()) {
            this.statusMessage = null
            textColor = "red"  // loom must be connected to weave
        }
        var statusElt = document.getElementById("status")
        statusElt.textContent = text
        statusElt.style.color = textColor
    }

    /*
    Display the current end numbers.
    */
    displayEnds() {
        var endNumber0Elt = document.getElementById("end_number0")
        var endNumber1Elt = document.getElementById("end_number1")
        var repeatNumberElt = document.getElementById("end_repeat_number")
        var totalEndsElt = document.getElementById("total_ends")
        var endNumber0 = ""
        var endNumber1 = ""
        var totalEnds = "?"
        var repeatNumber = ""
        if (this.currentPattern) {
            endNumber0 = this.currentPattern.end_number0
            endNumber1 = this.currentPattern.end_number1
            repeatNumber = this.currentPattern.end_repeat_number
            totalEnds = this.currentPattern.threading.length
        }
        endNumber0Elt.textContent = endNumber0
        endNumber1Elt.textContent = endNumber1
        repeatNumberElt.textContent = repeatNumber
        totalEndsElt.textContent = totalEnds
    }

    /*
    Display the current pick and repeat.
    */
    displayPick() {
        var repeatNumberElt = document.getElementById("pick_repeat_number")
        var pickNumberElt = document.getElementById("pick_number")
        var totalPicksElt = document.getElementById("total_picks")
        var pickNumber = ""
        var totalPicks = "?"
        var repeatNumber = ""
        if (this.currentPattern) {
            pickNumber = this.currentPattern.pick_number
            repeatNumber = this.currentPattern.pick_repeat_number
            totalPicks = this.currentPattern.picks.length
        }
        pickNumberElt.textContent = pickNumber
        repeatNumberElt.textContent = repeatNumber
        totalPicksElt.textContent = totalPicks
    }

    /*
    Display the jump end and repeat
    */
    displayJumpEnd() {
        var endNumber0Elt = document.getElementById("jump_end_number0")
        var repeatNumberElt = document.getElementById("jump_end_repeat_number")
        if (!this.currentPattern) {
            this.jumpEndNumber0 = null
            this.jumpEndRepeatNumber = null
        }
        endNumber0Elt.value = nullToBlank(this.jumpEndNumber)
        repeatNumberElt.value = nullToBlank(this.jumpEndRepeatNumber)
        if (this.currentPattern) {
            this.displayThreadingPattern()
        }
        this.handleJumpToEndInput(null)
    }

    /*
    Display the jump pick and repeat
    */
    displayJumpPick() {
        var pickNumberElt = document.getElementById("jump_pick_number")
        var repeatNumberElt = document.getElementById("jump_pick_repeat_number")
        if (!this.currentPattern) {
            this.jumpPickNumber = null
            this.jumpPickRepeatNumber = null
        }
        pickNumberElt.value = nullToBlank(this.jumpPickNumber)
        repeatNumberElt.value = nullToBlank(this.jumpPickRepeatNumber)
        if (this.currentPattern) {
            this.displayWeavingPattern()
        }
        this.handleJumpToPickInput(null)
    }

    /*
    Display the current mode
    */
    displayMode() {
        // Get all elements with class="tablinks" and remove the class "active"
        var buttons = document.getElementsByClassName("tabchoices")
        for (var button of buttons) {
            button.className = button.className.replace(" active", "")
        }

        var elt = null
        var modeButton = null
        if (this.mode == ModeEnum.THREADING) {
            modeButton = document.getElementById("mode_threading")
            for (const elt of document.getElementsByClassName("weaving")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("threading")) {
                elt.style.display = "flex"
            }
        } else {
            // weaving
            modeButton = document.getElementById("mode_weaving")
            for (const elt of document.getElementsByClassName("threading")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("weaving")) {
                elt.style.display = "flex"
            }
        }
        if (modeButton != null) {
            modeButton.className += " active"
        }
    }

    /*
    Display thread direction
    */
    displayThreadDirection() {
        var threadDirectionElt = document.getElementById("thread_direction")
        if (this.threadLowToHigh) {
            threadDirectionElt.textContent = "←"
        } else {
            threadDirectionElt.textContent = "→"
        }
    }

    /*
    Display a portion of threading on the "threading_canvas" element.
    
    Center the jump or current range horizontally.
    */
    displayThreadingPattern() {
        var canvas = document.getElementById("threading_canvas")
        var ctx = canvas.getContext("2d")
        if (!this.currentPattern) {
            ctx.clearRect(0, 0, canvas.width, canvas.height)
            return
        }
        var endNumber0 = this.currentPattern.end_number0
        var endNumber1 = this.currentPattern.end_number1
        var isJump = false
        if (this.jumpEndNumber0 != null) {
            isJump = true
            endNumber0 = this.jumpEndNumber0
            endNumber1 = Math.min(this.jumpEndNumber0 + this.threadGroupSize, this.currentPattern.threading.length) + 1
        }
        const centerEndNumber = Math.round(Math.max(0, (endNumber0 + endNumber1 - 1) / 2))
        ctx.font = EndFont
        ctx.textBaseline = "middle"
        ctx.textAlign = "center"
        const fontMeas = ctx.measureText("32")
        var blockWidth = Math.ceil(fontMeas.width) + EndDisplayGap
        if (blockWidth % 2 == 0) {
            blockWidth++
        }
        const blockHalfWidth = (blockWidth - 1) / 2
        var blockHeight = Math.ceil(fontMeas.actualBoundingBoxAscent + fontMeas.actualBoundingBoxDescent)
        if (blockHeight % 2 == 0) {
            blockHeight++
        }
        const numEnds = this.currentPattern.warp_colors.length
        const remainingHeight = canvas.height - (blockHeight + fontMeas.actualBoundingBoxAscent + fontMeas.actualBoundingBoxDescent)
        const maxShaftNum = Math.max(...this.currentPattern.threading) + 1
        const verticalDelta = Math.floor(Math.min(blockHeight, remainingHeight / maxShaftNum))

        const numEndsToShow = Math.min(numEnds, Math.floor(canvas.width / blockWidth))

        const centerSlotIndex = Math.round((numEndsToShow - 1) / 2)
        ctx.clearRect(0, 0, canvas.width, canvas.height)

        const maxColoredEndIndex = isJump ? endNumber0 - 2 : endNumber1 - 2

        // TODO: put a box about the current thread group

        // Display 2 end numbers: endNumber0 and, if there is space, endNumber1,
        // else endNumber0 + 2
        const displayEndNumber = Math.max(endNumber1 - 1, endNumber0 + 2)
        for (let slotIndex = 0; slotIndex < numEndsToShow; slotIndex++) {
            const endIndex = centerEndNumber + slotIndex - centerSlotIndex - 1

            if (endIndex < 0 || endIndex >= this.currentPattern.threading.length) {
                continue
            }
            if (endIndex > maxColoredEndIndex) {
                ctx.globalAlpha = 0.3
            } else {
                ctx.globalAlpha = 1.0
            }

            const shaftIndex = this.currentPattern.threading[endIndex]

            const xCenter = canvas.width - blockWidth * slotIndex - blockHalfWidth
            const yCenter = canvas.height - verticalDelta * (shaftIndex + 0.5) - fontMeas.actualBoundingBoxDescent

            if (endIndex == endNumber0 - 1) {
                ctx.fillStyle = "black"
                ctx.fillText(endIndex + 1,
                    xCenter,
                    fontMeas.actualBoundingBoxAscent + 2,
                )
                ctx.strokeRect(
                    xCenter + blockHalfWidth,
                    blockHeight + 2,
                    - blockWidth * (endNumber1 - endNumber0),
                    canvas.height - blockHeight - 2,
                )
            } else if (endIndex == displayEndNumber - 1) {
                ctx.fillStyle = "black"
                ctx.fillText(endIndex + 1,
                    xCenter,
                    fontMeas.actualBoundingBoxAscent + 2,
                )
            }

            // Display weft (end) color as bars above and below the shaft number
            const xStart = xCenter - ThreadHalfWidth
            const xEnd = xCenter + ThreadHalfWidth
            const endColor = this.currentPattern.color_table[this.currentPattern.warp_colors[endIndex]]
            var endGradient = ctx.createLinearGradient(xStart, 0, xEnd, 0)
            endGradient.addColorStop(0, "white")
            endGradient.addColorStop(0.2, endColor)
            endGradient.addColorStop(0.8, endColor)
            endGradient.addColorStop(1, "gray")

            ctx.fillStyle = endGradient
            ctx.fillRect(
                xCenter - ThreadHalfWidth,
                blockHeight + 2,
                ThreadHalfWidth * 2,
                yCenter - Math.round(blockHeight / 2) - blockHeight - 4,
            )
            ctx.fillRect(
                xCenter - ThreadHalfWidth,
                yCenter + Math.round(blockHeight / 2) + 2,
                ThreadHalfWidth * 2,
                canvas.height - (yCenter + Math.round(blockHeight / 2) + 2)
            )

            // Display shaft number
            ctx.fillStyle = "black"
            ctx.fillText(shaftIndex + 1,
                xCenter,
                yCenter
            )
        }
    }

    // Display the weave direction -- the value of the global "weaveForward" 
    displayWeaveDirection() {
        var weaveDirectionElt = document.getElementById("weave_direction")
        if (this.weaveForward) {
            weaveDirectionElt.textContent = "↓"
            weaveDirectionElt.style.color = "green"
        } else {
            weaveDirectionElt.textContent = "↑"
            weaveDirectionElt.style.color = "red"
        }
    }

    /*
    Display weaving pattern on the "pattern_canvas" element.
 
    Center the jump or current pick vertically.
    */
    displayWeavingPattern() {
        var pickColorElt = document.getElementById("pick_color")
        var canvas = document.getElementById("pattern_canvas")
        var ctx = canvas.getContext("2d")
        if (!this.currentPattern) {
            ctx.clearRect(0, 0, canvas.width, canvas.height)
            pickColorElt.style.backgroundColor = "rgb(0, 0, 0, 0)"
            return
        }
        var centerPickNumber = this.currentPattern.pick_number
        var isJump = false
        if (this.jumpPickNumber != null) {
            isJump = true
            centerPickNumber = this.jumpPickNumber
        }
        if ((centerPickNumber > 0) && (centerPickNumber <= this.currentPattern.picks.length)) {
            const pick = this.currentPattern.picks[centerPickNumber - 1]
            pickColorElt.style.backgroundColor = this.currentPattern.color_table[pick.color]
        } else {
            pickColorElt.style.backgroundColor = "rgb(0, 0, 0, 0)"
        }
        const numEnds = this.currentPattern.warp_colors.length
        const numPicks = this.currentPattern.picks.length
        var blockSize = Math.min(
            Math.max(Math.round(canvas.width / numEnds), MinBlockSize),
            Math.max(Math.round(canvas.height / numPicks), MinBlockSize),
            MaxBlockSize)
        // Make sure blockSize is odd
        if (blockSize % 2 == 0) {
            blockSize -= 1
        }

        const numEndsToShow = Math.min(numEnds, Math.floor(canvas.width / blockSize))
        // Make sure numPicksToShow is odd
        var numPicksToShow = Math.min(numPicks, Math.ceil(canvas.height / blockSize))
        if (numPicksToShow % 2 == 0) {
            numPicksToShow += 1
        }

        // If not yet done, create warp gradients for those warps what will be shown
        if (this.currentPattern.warpGradients[0] == undefined) {
            for (let i = 0; i < numEndsToShow; i++) {
                const threadColor = this.currentPattern.color_table[this.currentPattern.warp_colors[i]]
                const xStart = canvas.width - blockSize * (i + 1)
                var warpGradient = ctx.createLinearGradient(xStart + ThreadDisplayGap, 0, xStart + blockSize - (2 * ThreadDisplayGap), 0)
                warpGradient.addColorStop(0, "white")
                warpGradient.addColorStop(0.2, threadColor)
                warpGradient.addColorStop(0.8, threadColor)
                warpGradient.addColorStop(1, "gray")
                this.currentPattern.warpGradients[i] = warpGradient
            }
        }
        var yOffset = Math.floor((canvas.height - (blockSize * numPicksToShow)) / 2)
        var startPick = centerPickNumber - ((numPicksToShow - 1) / 2)
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        var maxColoredPickIndex = centerPickNumber - 1
        if (isJump) {
            maxColoredPickIndex -= 1
        }
        for (let pickOffset = 0; pickOffset < numPicksToShow; pickOffset++) {
            const pickIndex = startPick + pickOffset - 1

            if (pickIndex < 0 || pickIndex >= this.currentPattern.picks.length) {
                continue
            }
            if (pickIndex > maxColoredPickIndex) {
                ctx.globalAlpha = 0.3
            } else {
                ctx.globalAlpha = 1.0
            }

            const yStart = canvas.height - (yOffset + (blockSize * (pickOffset + 1)))
            var pickGradient = ctx.createLinearGradient(0, yStart + ThreadDisplayGap, 0, yStart + blockSize - (2 * ThreadDisplayGap))
            const pickColor = this.currentPattern.color_table[this.currentPattern.picks[pickIndex].color]
            pickGradient.addColorStop(0, "white")
            pickGradient.addColorStop(0.2, pickColor)
            pickGradient.addColorStop(0.8, pickColor)
            pickGradient.addColorStop(1, "gray")

            const shaft_word = this.currentPattern.picks[pickIndex].shaft_word
            for (let end = 0; end < numEndsToShow; end++) {
                const shaft = this.currentPattern.threading[end]
                if (shaft_word & (1n << BigInt(shaft))) {
                    // Display warp end
                    ctx.fillStyle = this.currentPattern.warpGradients[end]
                    ctx.fillRect(
                        canvas.width - blockSize * (end + 1) + ThreadDisplayGap,
                        yStart,
                        blockSize - (2 * ThreadDisplayGap),
                        blockSize)
                } else {
                    // Display weft pick
                    ctx.fillStyle = pickGradient
                    ctx.fillRect(
                        canvas.width - blockSize * (end + 1),
                        yStart + ThreadDisplayGap,
                        blockSize,
                        blockSize - (2 * ThreadDisplayGap))
                }
            }

        }

        ctx.globalAlpha = 1.0
        if (isJump) {
            // Jump pick: draw a dashed line around the (centered) jump pick,
            // and, if on the canvas, a solid line around the current pick
            const jumpPickOffset = this.jumpPickNumber - startPick
            ctx.setLineDash([1, 3])
            ctx.strokeRect(
                0,
                canvas.height - (yOffset + (blockSize * (jumpPickOffset + 1))),
                canvas.width,
                blockSize)
            ctx.setLineDash([])
            const currentPickOffset = this.currentPattern.pick_number - startPick
            if ((currentPickOffset >= 0) && (currentPickOffset < numPicksToShow)) {
                ctx.strokeRect(
                    0,
                    canvas.height - (yOffset + (blockSize * (currentPickOffset + 1))),
                    canvas.width,
                    blockSize)
            }
        } else {
            // No jump pick number; draw a solid line around the (centered) current pick
            ctx.setLineDash([])
            const currentPickOffset = this.currentPattern.pick_number - startPick
            ctx.strokeRect(
                0,
                canvas.height - (yOffset + (blockSize * (currentPickOffset + 1))),
                canvas.width,
                blockSize)
        }
    }

    /*
    Handle the pattern_menu select menu.
    
    Send the "select_pattern" or "clear_pattern_names" command.
    */
    async handlePatternMenu(event) {
        var patternMenu = document.getElementById("pattern_menu")
        var command
        if (patternMenu.value == "Clear Recents") {
            command = { "type": "clear_pattern_names" }
        } else {
            command = { "type": "select_pattern", "name": patternMenu.value }
        }
        await this.sendCommand(command)
    }

    /*
    Handle pattern files dropped on drop area (likely the whole page)
    */
    async handleDrop(event) {
        await this.handleFileList(event.dataTransfer.files)
    }

    /*
    Handle pattern files from the file_list button
    */
    async handleFileInput(event) {
        await this.handleFileList(event.target.files)
    }

    /*
    Handle pattern file upload from the button and drag-and-drop
    (the latter after massaging the data with handleDrop).
    
    Send the "file" and "select_pattern" commands.
    */
    async handleFileList(fileList) {
        if (fileList.length > MaxFiles) {
            console.log("Cannot upload more than", MaxFiles, "files at once")
            return
        }
        if (fileList.length == 0) {
            return
        }

        // Sort the file names; this requires a bit of extra work
        // because FileList doesn't support sort.

        var fileArray = Array.from(fileList)
        fileArray.sort(compareFiles)

        for (var file of fileArray) {
            var data = await readTextFile(file)
            var fileCommand = { "type": "file", "name": file.name, "data": data }
            await this.sendCommand(fileCommand)
        }

        // Select the first file uploaded
        var file = fileArray[0]
        var selectPatternCommand = { "type": "select_pattern", "name": file.name }
        await this.sendCommand(selectPatternCommand)
    }

    /*
    Handle the thread group size select menu
    */
    async handleThreadGroupSize(event) {
        var patternMenu = document.getElementById("thread_group_size")
        const command = { "type": "thread_group_size", "group_size": Number(patternMenu.value) }
        await this.sendCommand(command)
    }


    /*
    Handle user editing of jump_end_number and jump_end_repeat_number.
    */
    async handleJumpToEndInput(event) {
        var jumpToEndSubmitElt = document.getElementById("jump_to_end_submit")
        var jumpToEndResetElt = document.getElementById("jump_to_end_reset")
        var jumpEndNumber0Elt = document.getElementById("jump_end_number0")
        var jumpEndRepeatNumberElt = document.getElementById("jump_end_repeat_number")
        var disableJump = true
        if (asNumberOrNull(jumpEndNumber0Elt.value) != this.jumpEndNumber) {
            jumpEndNumber0Elt.style.backgroundColor = "pink"
            disableJump = false
        } else {
            jumpEndNumber0Elt.style.backgroundColor = "white"
        }
        if (asNumberOrNull(jumpEndRepeatNumberElt.value) != this.jumpEndRepeatNumber) {
            jumpEndRepeatNumberElt.style.backgroundColor = "pink"
            disableJump = false
        } else {
            jumpEndRepeatNumberElt.style.backgroundColor = "white"
        }
        var disableReset = disableJump && (jumpEndNumber0Elt.value == "") && (jumpEndRepeatNumberElt.value == "")
        jumpToEndSubmitElt.disabled = disableJump
        jumpToEndResetElt.disabled = disableReset
        if (event != null) {
            event.preventDefault()
        }
    }

    /*
    Handle Reset buttin in the "jump_to_end" form.
    
    Reset end number and repeat number to current values.
    */
    async handleJumpToEndReset(event) {
        const jumpEndNumber0Elt = document.getElementById("jump_end_number0")
        const jumpEndRepeatNumberElt = document.getElementById("jump_end_repeat_number")
        jumpEndNumber0Elt.value = ""
        jumpEndRepeatNumberElt.value = ""
        const command = { "type": "jump_to_end", "end_number0": null, "end_repeat_number": null }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle jump_to_end form submit.
    
    Send the "jump_to_end" command.
    */
    async handleJumpToEndSubmit(event) {
        const jumpEndNumber0Elt = document.getElementById("jump_end_number0")
        const jumpEndRepeatNumberElt = document.getElementById("jump_end_repeat_number")
        // Handle blanks by using the current default, if any
        const endNumber0 = asNumberOrNull(jumpEndNumber0Elt.value)
        const repeatNumber = asNumberOrNull(jumpEndRepeatNumberElt.value)
        const command = { "type": "jump_to_end", "end_number0": endNumber0, "end_repeat_number": repeatNumber }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle user editing of jump_pick_number and jump_pick_repeat_number.
    */
    async handleJumpToPickInput(event) {
        var jumpToPickSubmitElt = document.getElementById("jump_to_pick_submit")
        var jumpToPickResetElt = document.getElementById("jump_to_pick_reset")
        var jumpPickNumberElt = document.getElementById("jump_pick_number")
        var jumpPickRepeatNumberElt = document.getElementById("jump_pick_repeat_number")
        var disableJump = true
        if (asNumberOrNull(jumpPickNumberElt.value) != this.jumpPickNumber) {
            jumpPickNumberElt.style.backgroundColor = "pink"
            disableJump = false
        } else {
            jumpPickNumberElt.style.backgroundColor = "white"
        }
        if (asNumberOrNull(jumpPickRepeatNumberElt.value) != this.jumpPickRepeatNumber) {
            jumpPickRepeatNumberElt.style.backgroundColor = "pink"
            disableJump = false
        } else {
            jumpPickRepeatNumberElt.style.backgroundColor = "white"
        }
        var disableReset = disableJump && (jumpPickNumberElt.value == "") && (jumpPickRepeatNumberElt.value == "")
        jumpToPickSubmitElt.disabled = disableJump
        jumpToPickResetElt.disabled = disableReset
        if (event != null) {
            event.preventDefault()
        }
    }

    /*
    Handle Reset buttin in the "jump_to_pick" form.
    
    Reset pick number and repeat number to current values.
    */
    async handleJumpToPickReset(event) {
        const jumpPickNumberElt = document.getElementById("jump_pick_number")
        const jumpPickRepeatNumberElt = document.getElementById("jump_pick_repeat_number")
        jumpPickNumberElt.value = ""
        jumpPickRepeatNumberElt.value = ""
        const command = { "type": "jump_to_pick", "pick_number": null, "pick_repeat_number": null }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle jump_to_pick form submit.
    
    Send the "jump_to_pick" command.
    */
    async handleJumpToPickSubmit(event) {
        const jumpPickNumberElt = document.getElementById("jump_pick_number")
        const jumpPickRepeatNumberElt = document.getElementById("jump_pick_repeat_number")
        // Handle blanks by using the current default, if any
        const pickNumber = asNumberOrNull(jumpPickNumberElt.value)
        const repeatNumber = asNumberOrNull(jumpPickRepeatNumberElt.value)
        const command = { "type": "jump_to_pick", "pick_number": pickNumber, "pick_repeat_number": repeatNumber }
        await this.sendCommand(command)
        event.preventDefault()
    }


    /*
    Handle the OOB change direction button.
    
    Send "oobcommand" command "d".
    */
    async handleOOBChangeDirection(event) {
        var command = { "type": "oobcommand", "command": "d" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the OOB close connection button.
    
    Send "oobcommand" command "c".
    */
    async handleOOBCloseConnection(event) {
        var command = { "type": "oobcommand", "command": "c" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the OOB next pick button.
    
    Send "oobcommand" command "n".
    */
    async handleOOBNextPick(event) {
        var command = { "type": "oobcommand", "command": "n" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the mode tab bar buttons

    Mode us a ModeEnum value
    */
    async handleMode(mode, event) {
        var command = { "type": "mode", "mode": mode }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle thread_direction button clicks.
    
    Send the weave_direction command to the loom server.
    */
    async handleToggleThreadDirection(event) {
        var threadDirectionElt = document.getElementById("thread_direction")
        var newLowToHigh = (threadDirectionElt.textContent == "→") ? true : false
        var command = { "type": "thread_direction", "low_to_high": newLowToHigh }
        await this.sendCommand(command)
    }

    /*
    Handle weave_direction button clicks.
    
    Send the weave_direction command to the loom server.
    */
    async handleToggleWeaveDirection(event) {
        var weaveDirectionElt = document.getElementById("weave_direction")
        var newForward = (weaveDirectionElt.textContent == "↑") ? true : false
        var command = { "type": "weave_direction", "forward": newForward }
        await this.sendCommand(command)
    }

    async sendCommand(commandDict) {
        var commandElt = document.getElementById("sent_command")
        var commandStr = JSON.stringify(commandDict)
        if (commandStr.length <= 80) {
            commandElt.textContent = commandStr
        } else {
            commandElt.textContent = commandStr.substring(0, 80) + "..."
        }
        await this.ws.send(commandStr)
    }
}

/*
Handle websocket close
*/
async function handleWebsocketClosed(event) {
    var statusElt = document.getElementById("status")
    statusElt.textContent = t("lost connection to server") + `: ${event.reason} `
    statusElt.style.color = "red"
}

/*
Return "" if value is null, else return value
*/
function nullToBlank(value) {
    return value == null ? "" : value
}

/*
Return null if value is "", else return Number(value)
*/
function asNumberOrNull(value) {
    return value == "" ? null : Number(value)
}

//
function preventDefaults(event) {
    event.preventDefault()
    event.stopPropagation()
}

// Async wrapper around FileReader.readAsText
// from https://masteringjs.io/tutorials/fundamentals/filereader#:~:text=The%20FileReader%20class%27%20async%20API%20isn%27t%20ideal,for%20usage%20with%20async%2Fawait%20or%20promise%20chaining.
function readTextFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()

        reader.onload = res => {
            resolve(res.target.result)
        }
        reader.onerror = err => reject(err)

        reader.readAsText(file)
    })
}

loomClient = new LoomClient()
loomClient.init()
