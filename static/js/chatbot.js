const chatbot = document.getElementById('chatbot-container');

const closeBtn    = document.getElementById('close-chat');
const minimiseBtn = document.getElementById('minimise-chat');

const sendBtn = document.getElementById('send-btn');

const inputField = document.getElementById('chat-input');

const chatMessages = document.getElementById('chat-messages');


// Show chatbot after 5 seconds
setTimeout(() => {

    chatbot.classList.remove('chatbot-hidden');

}, 5000);


// Close chatbot
closeBtn.addEventListener('click', () => {

    chatbot.style.display = 'none';

});


// Minimise / restore chatbot
minimiseBtn.addEventListener('click', () => {

    const isMinimised = chatbot.classList.toggle('chatbot-minimised');
    minimiseBtn.textContent = isMinimised ? '+' : '–';

});


// Send button click
sendBtn.addEventListener('click', sendMessage);


// Enter key support
inputField.addEventListener('keypress', function(event) {

    if (event.key === 'Enter') {
        sendMessage();
    }

});


// Send message to backend
async function sendMessage() {

    const message = inputField.value.trim();

    if (!message) return;


    // Add user message
    addMessage(message, 'user-message');

    inputField.value = '';
    sendBtn.disabled = true;


    // Show typing indicator
    const indicator = document.createElement('div');
    indicator.classList.add('typing-indicator');
    indicator.id = 'typing-indicator';
    indicator.innerHTML = '<span></span><span></span><span></span>';
    chatMessages.appendChild(indicator);
    chatMessages.scrollTop = chatMessages.scrollHeight;


    try {

        const response = await fetch('/api/chat', {

            method: 'POST',

            headers: {
                'Content-Type': 'application/json'
            },

            body: JSON.stringify({
                message: message
            })

        });


        const data = await response.json();

        indicator.remove();
        addMessage(data.reply, 'bot-message');

    }

    catch (error) {

        indicator.remove();
        addMessage(
            'Server connection error.',
            'bot-message'
        );

    }

    finally {
        sendBtn.disabled = false;
    }

}


// Add messages to chat window
function addMessage(text, className) {

    const messageDiv = document.createElement('div');

    messageDiv.classList.add(className);

    text.split('\n').forEach((line, i) => {
        if (i > 0) messageDiv.appendChild(document.createElement('br'));
        messageDiv.appendChild(document.createTextNode(line));
    });

    chatMessages.appendChild(messageDiv);

    chatMessages.scrollTop = chatMessages.scrollHeight;

}
