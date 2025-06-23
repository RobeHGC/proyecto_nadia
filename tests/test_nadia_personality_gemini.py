import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from agents.supervisor_agent import SupervisorAgent


class TestNadiaPersonalityGemini:
    """Tests for the new NADIA personality implementation in Gemini LLM-1."""
    
    @pytest.fixture
    async def supervisor_agent(self):
        """Create a supervisor agent for testing."""
        # Mock dependencies
        mock_llm_client = AsyncMock()
        mock_memory = AsyncMock()
        mock_config = Mock()
        
        # Configure mock config
        mock_config.llm_profile = 'testing'
        mock_config.llm1_provider = 'gemini'
        mock_config.llm1_model = 'gemini-2.0-flash-exp'
        mock_config.llm2_provider = 'openai'
        mock_config.llm2_model = 'gpt-4o-mini'
        mock_config.gemini_api_key = 'test-key'
        mock_config.openai_api_key = 'test-key'
        
        agent = SupervisorAgent(
            llm_client=mock_llm_client,
            memory=mock_memory,
            config=mock_config
        )
        
        # Override with mocks for testing
        agent.llm1 = AsyncMock()
        agent.llm2 = AsyncMock()
        agent.llm_router = None  # Disable router for simpler testing
        agent.logger = Mock()
        agent.constitution = Mock()
        
        return agent
    
    async def test_monterrey_identity(self, supervisor_agent):
        """Verifica identidad de Monterrey."""
        # Mock LLM response
        supervisor_agent.llm1.generate_response.return_value = "I'm from Monterrey, Nuevo León! It's a beautiful city in Mexico 😊"
        supervisor_agent.llm2.generate_response.return_value = "I'm from Monterrey, Nuevo León! [GLOBO] It's a beautiful city in Mexico 😊"
        supervisor_agent.constitution.analyze.return_value = {'risk_score': 0.1, 'flags': []}
        supervisor_agent.memory.get_conversation_history.return_value = []
        supervisor_agent.memory.add_to_conversation_history = AsyncMock()
        
        response = await supervisor_agent.process_message("123", "Where are you from?")
        text = response.ai_suggestion.llm1_raw.lower()
        
        # Debe mencionar Monterrey o Nuevo León
        assert any(word in text for word in ["monterrey", "nuevo león", "mexico"])
    
    async def test_medical_student_identity(self, supervisor_agent):
        """Verifica que mencione ser estudiante de medicina."""
        # Mock LLM response
        supervisor_agent.llm1.generate_response.return_value = "I'm a medical student at UDEM! Studying to be a pediatrician 😊"
        supervisor_agent.llm2.generate_response.return_value = "I'm a medical student at UDEM! [GLOBO] Studying to be a pediatrician 😊"
        supervisor_agent.constitution.analyze.return_value = {'risk_score': 0.1, 'flags': []}
        supervisor_agent.memory.get_conversation_history.return_value = []
        supervisor_agent.memory.add_to_conversation_history = AsyncMock()
        
        response = await supervisor_agent.process_message("123", "What do you do?")
        text = response.ai_suggestion.llm1_raw.lower()
        
        assert any(word in text for word in ["medical", "medicine", "student", "udem"])
    
    async def test_characteristic_words(self, supervisor_agent):
        """Verifica uso de palabras características."""
        # Mock responses with characteristic words
        responses_mock = [
            "That's so cool wey! lol 😊",
            "Dude that sounds amazing! xd",
            "Hahaha bro you're funny! jejejej"
        ]
        
        supervisor_agent.llm1.generate_response.side_effect = responses_mock
        supervisor_agent.llm2.generate_response.side_effect = [r + " [GLOBO]" for r in responses_mock]
        supervisor_agent.constitution.analyze.return_value = {'risk_score': 0.1, 'flags': []}
        supervisor_agent.memory.get_conversation_history.return_value = []
        supervisor_agent.memory.add_to_conversation_history = AsyncMock()
        
        responses = []
        prompts = ["That's cool!", "Tell me more", "How was your day?"]
        
        for prompt in prompts:
            r = await supervisor_agent.process_message("123", prompt)
            responses.append(r.ai_suggestion.llm1_raw.lower())
        
        all_text = " ".join(responses)
        words = ["wey", "dude", "lol", "bro", "xd", "haha", "jeje"]
        
        # Al menos debe usar algunas
        found = sum(1 for word in words if word in all_text)
        assert found >= 2
    
    async def test_anti_interrogation_logic(self, supervisor_agent):
        """Verifica que la lógica anti-interrogatorio funcione."""
        # Setup: previous message had a question
        previous_history = [
            {'role': 'user', 'content': 'How are you?'},
            {'role': 'assistant', 'content': 'Good! How about you?'}  # Has question
        ]
        
        supervisor_agent.memory.get_conversation_history.return_value = previous_history
        supervisor_agent.memory.add_to_conversation_history = AsyncMock()
        
        # Build prompt to check anti-interrogation logic
        prompt = await supervisor_agent._build_creative_prompt("I'm good too", {'user_id': '123'})
        
        # Check that anti-interrogation instruction is included
        system_messages = [msg for msg in prompt if msg['role'] == 'system']
        anti_interrogation_found = any(
            'do not ask another question' in msg['content'].lower() 
            for msg in system_messages
        )
        
        assert anti_interrogation_found, "Anti-interrogation instruction should be present when previous message had a question"
    
    async def test_face_emojis_only(self, supervisor_agent):
        """Verifica que solo use emojis de cara específicos."""
        # Mock response with face emojis
        supervisor_agent.llm1.generate_response.return_value = "That's great! 😊 I'm happy for you 😅"
        supervisor_agent.llm2.generate_response.return_value = "That's great! 😊 [GLOBO] I'm happy for you 😅"
        supervisor_agent.constitution.analyze.return_value = {'risk_score': 0.1, 'flags': []}
        supervisor_agent.memory.get_conversation_history.return_value = []
        supervisor_agent.memory.add_to_conversation_history = AsyncMock()
        
        # Build prompt to check emoji guidelines
        prompt = await supervisor_agent._build_creative_prompt("Good news!", {'user_id': '123'})
        
        # Check that face emoji instruction is in the persona
        persona_content = prompt[0]['content']
        assert '😊😅🥰😌🤔' in persona_content
        assert 'Use face emojis only, max 2 per complete response' in persona_content
    
    async def test_medical_boundary(self, supervisor_agent):
        """Verifica que maneje preguntas médicas apropiadamente."""
        # Build prompt for medical question
        prompt = await supervisor_agent._build_creative_prompt("I have a headache, what should I do?", {'user_id': '123'})
        
        # Check that medical boundary is in the persona
        persona_content = prompt[0]['content']
        assert 'You should definitely see a doctor! I\'m still learning' in persona_content
        assert 'Medical questions →' in persona_content
    
    async def test_conversation_history_inclusion(self, supervisor_agent):
        """Verifica que incluya historial de conversación."""
        # Setup conversation history
        history = [
            {'role': 'user', 'content': 'Hi there!'},
            {'role': 'assistant', 'content': 'Hey! How are you?'},
            {'role': 'user', 'content': 'I\'m good'},
            {'role': 'assistant', 'content': 'That\'s great to hear!'}
        ]
        
        supervisor_agent.memory.get_conversation_history.return_value = history
        
        # Build prompt
        prompt = await supervisor_agent._build_creative_prompt("What's your favorite music?", {'user_id': '123'})
        
        # Check that recent conversation is included
        history_messages = [msg for msg in prompt if 'Recent conversation:' in msg.get('content', '')]
        assert len(history_messages) == 1
        
        # Should include last 6 messages (3 exchanges)
        history_content = history_messages[0]['content']
        assert 'User: Hi there!' in history_content
        assert 'Nadia: Hey! How are you?' in history_content