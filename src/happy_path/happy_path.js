// ---------------------------------------------
// Constants and variables.
// ---------------------------------------------
const started = new Date().getTime();
const duration = 1000;
var playing = true;
var cursor = 0;
var step = 1;
var edges = [];
var events = [];

// ---------------------------------------------
// Utilities.
// ---------------------------------------------
function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

function readTextFile(file, callback) {
    var rawFile = new XMLHttpRequest();
    rawFile.open("GET", file, true);
    rawFile.onreadystatechange = function() {
        if (rawFile.readyState === 4 && rawFile.status == "200") {
            callback(rawFile.responseText);
        }
    }
    rawFile.send(null);
}

// ---------------------------------------------
// Graph manipulation.
// ---------------------------------------------
function initGraph() {
    const graph = document.getElementById('graph0');

    // Add a circle to represent the moving circle.
    const movingCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    movingCircle.setAttribute('id', 'movingCircle');
    movingCircle.setAttribute('r', '10');
    movingCircle.setAttribute('fill', 'blue');
    graph.appendChild(movingCircle);

    // Set the id of each edge path and store it in the edges array.
    for (const edgePath of document.querySelectorAll('.edge > path')) {
        const edgePathId = edgePath.parentElement.getAttribute('id') + '-path';
        edgePath.setAttribute('id', edgePathId);
        edges.push(edgePathId)
    }
}

function resetCircle(circle) {
    circle.setAttribute('cx', 0);
    circle.setAttribute('cy', 0);
}

function showCircle(circle) {
    circle.style.display = 'block';
}

function hideCircle(circle) {
    circle.style.display = 'none';
}

function placeCircleAtEdgeEnd(circle, pathId) {
    const path = document.getElementById(pathId);
    const pathLength = path.getTotalLength();
    const { x, y } = path.getPointAtLength(pathLength);
    circle.setAttribute('cx', x);
    circle.setAttribute('cy', y);
}

function placeCircleAtEdgeStart(circle, pathId) {
    const path = document.getElementById(pathId);
    const { x, y } = path.getPointAtLength(0);
    circle.setAttribute('cx', x);
    circle.setAttribute('cy', y);
}

function moveCircleAlongEdge(eventNumber, dur) {
    const event = events[eventNumber];
    const pathId = event.caller.name + '--' + event.callee.name + "-path";
    const [stackAbove, stackBelow] = stacks(eventNumber);
    const mpath = document.createElementNS('http://www.w3.org/2000/svg', 'mpath');
    const animateMotion = document.createElementNS('http://www.w3.org/2000/svg', 'animateMotion');
    const movingCircle = document.getElementById('movingCircle');

    mpath.setAttribute('href', '#' + pathId);
    animateMotion.appendChild(mpath);
    animateMotion.setAttribute('dur', dur);
    animateMotion.setAttribute('repeatCount', '1');
    animateMotion.setAttribute('begin', (new Date().getTime() - started) / 1000);
    if (event.event === 'return') {
        animateMotion.setAttribute('keyPoints', '1;0');
        animateMotion.setAttribute('keyTimes', '0;1');
    }
    movingCircle.appendChild(animateMotion);
    animateMotion.addEventListener('beginEvent', function() {
        clearStackMarks();
        markStackAbove(stackAbove.slice(1));
        markStackBelow(stackBelow.slice(1));
        if (event.event === 'return') {
            markCurrentNodeReturned(event);
            movingCircle.setAttribute('fill', 'blueviolet');
        }
        else {
            markCurrentNodeCalled(event);
            movingCircle.setAttribute('fill', 'blue');
        }
        showCircle(movingCircle);
    });
    animateMotion.addEventListener('endEvent', function() {
        hideCircle(movingCircle);
        movingCircle.removeChild(animateMotion);
        clearStackMarks();
        markStackAbove(stackAbove);
        markStackBelow(stackBelow);
        if (event.event === 'call') {
            markCurrentNode(event.callee.name);
        }
        else {
            markCurrentNode(event.caller.name);
        }
    });
}

function stacks(eventNumber) {
    var stackAbove = [];
    var stackBelow = [];

    while (eventNumber >= 0 && events[eventNumber].event === 'return') {
        stackBelow.push(events[eventNumber]);
        eventNumber--;
    }

    var skipCalls = 0;
    while (eventNumber >= 0) {
        const event = events[eventNumber];
        if (event.event === 'return') {
            skipCalls++;
        }
        else if (skipCalls > 0) {
            skipCalls--;
        }
        else {
            stackAbove.push(event);
        }
        eventNumber--;
    }

    return [stackAbove, stackBelow];
}

function clearStackMarks() {
    for (const element of document.querySelectorAll('.sa, .sb, .sc')) {
        element.classList.remove('sa', 'sb', 'sc');
    }
}

function markStackAbove(stack) {
    stack.forEach(event => {
        const pathId = event.caller.name + '--' + event.callee.name;
        const path = document.getElementById(pathId);
        path.classList.add('sa');
        const endNode = document.getElementById(event.callee.name);
        endNode.classList.add('sa');
    });
    if (stack.length > 0) {
        const startNode = document.getElementById(stack[stack.length - 1].caller.name);
        startNode.classList.add('sa');
    }
}

function markStackBelow(stack) {
    stack.forEach(event => {
        const pathId = event.caller.name + '--' + event.callee.name;
        const path = document.getElementById(pathId);
        path.classList.add('sb');
        const startNode = document.getElementById(event.caller.name);
        startNode.classList.add('sb');
    });
    if (stack.length > 0) {
        const endNode = document.getElementById(stack[stack.length - 1].callee.name);
        endNode.classList.add('sb');
    }
}

function markCurrentNode(nodeName) {
    const node = document.getElementById(nodeName);
    node.classList.remove('sa', 'sb');
    node.classList.add('sc');
}

function markCurrentNodeCalled(event) {
    const node = document.getElementById(event.caller.name);
    node.classList.remove('sb', 'sc');
    node.classList.add('sa');
}

function markCurrentNodeReturned(event) {
    const node = document.getElementById(event.callee.name);
    node.classList.remove('sa', 'sc');
    node.classList.add('sb');
}

// ---------------------------------------------
// Interactive controls.
// ---------------------------------------------
async function play() {
    // iterate through events and trigger animations
    playing = true;
    for (let i = cursor; (i >= 0 && i < events.length); i+=step) {
        moveCircleAlongEdge(i, duration / 1000 + 's');
        cursor = i + step;
        if (!playing) break;
        await sleep(duration * 2);
    }
}

function pause() {
    playing = false;
}

function stepForward() {
    if (cursor < events.length) {
        moveCircleAlongEdge(cursor, duration / 1000 + 's');
        cursor++;
    }
}

function stepBackward() {
    if (cursor > 0) {
        cursor--;
        const [stackAbove, stackCurrent, stackBelow] = stacks(cursor-1);
        clearStackMarks();
        markStackAbove(stackAbove);
        markStackCurrent(stackCurrent);
        markStackBelow(stackBelow);
    }
}

function stepOut() {
    console.log("not implmented");
}

// ---------------------------------------------
// Main function.
// ---------------------------------------------
function happyPath(eventsUrl="events.jsonl") {
    document.getElementById('pressPlay').addEventListener('click', play);
    document.getElementById('pressPause').addEventListener('click', pause);
    document.getElementById('pressStepForward').addEventListener('click', stepForward);
    document.getElementById('pressStepBackward').addEventListener('click', stepBackward);
    document.getElementById('pressStepOut').addEventListener('click', stepOut);

    initGraph();

    readTextFile(eventsUrl, function(jsonl) {
        jsonl.split(/\n/).forEach(line => {
            if (line.length > 0) {
                events.push(JSON.parse(line));
            }
        });
        play();
    });
}
