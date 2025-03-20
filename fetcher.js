const { Pull, Push } = require('zeromq');

// Pull Socket: MT5 -> Node JS
const pullSock = new Pull();

// Push Socket: Node JS -> Spring Boot Application
const pushSock = new Push();

async function connectPullSocket() {
    try {
        pullSock.connect('tcp://127.0.0.1:5555');
        console.log('Pull socket connected to tcp://127.0.0.1:5555');

        // Set socket options to improve reliability
        pullSock.receiveTimeout = -1; // No timeout, wait indefinitely for messages
        pullSock.linger = 0; // Discard messages immediately on close
    } catch (error) {
        console.error('Error connecting pull socket:', error.message);
        setTimeout(connectPullSocket, 5000);
    }
}

async function bindPushSocket() {
    try {
        pushSock.bind('tcp://127.0.0.1:5556');
        console.log('Push socket bound to tcp://127.0.0.1:5556');
    } catch (error) {
        console.error('Error binding push socket:', error.message);
        process.exit(1); // Exit on binding failure
    }
}

// Main function to pull and forward messages
(async () => {
    try {
        // Initialize sockets
        await connectPullSocket();
        await bindPushSocket();

        console.log('Listening for messages...');
        while (true) { // Continuous message pulling
            try {
                const msg = await pullSock.receive(); // Wait for a message
                const message = msg.toString(); // Convert buffer to string
                console.log('Received from EA:', message);

                // Forward the message to Spring Boot
                await pushSock.send(message);
                console.log('Forwarded to Spring Boot:', message);
            } catch (error) {
                console.error('Error receiving or forwarding message:', error.message);
                // Attempt to reconnect pull socket on error
                await connectPullSocket();
            }
        }
    } catch (error) {
        console.error('Fatal error:', error.message);
        process.exit(1); // Exit on unrecoverable error
    }
})();

// Handle process termination
process.on('SIGINT', () => {
    pullSock.close();
    pushSock.close();
    console.log('Sockets closed');
    process.exit();
});