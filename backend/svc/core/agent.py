import os
import logging
import json
from datetime import datetime
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import openai
from agentmail import AgentMail
import ngrok
from jinja2 import Template

from langchain.agents import AgentExecutor, create_react_agent, create_tool_calling_agent
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from svc.core.config import (
    DEFAULT_RESUME_DIR, AGENTMAIL_API_KEY, DEFAULT_AGENDA_COLLECTION, DEFAULT_BUCKET, DEFAULT_SCOPE, DEFAULT_COLLECTION, DEFAULT_INDEX,
    CAPELLA_API_ENDPOINT, CAPELLA_API_EMBEDDINGS_KEY, CAPELLA_API_EMBEDDING_MODEL, CAPELLA_API_LLM_KEY, CAPELLA_API_LLM_MODEL,
    OPENAI_API_KEY, INBOX_USERNAME, PORT, WEBHOOK_DOMAIN, SERVER_URL
)
from svc.core.db import CouchbaseClient, test_capella_connectivity
from agentc import Catalog

logger = logging.getLogger("uvicorn.error" )

# Initialize OpenAI client
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


class AgentManager:
    """Manager class for AI services and agent components."""

    def __init__(self, couchbase_client):
        self.agent_executor = None
        self.email_agent_executor = None
        self.embeddings = None
        self.llm = None
        self.couchbase_client = couchbase_client
        self.catalog = None
        self.processed_messages = set()

    def setup_ai_services(self, temperature: float = 0.0, use_capella: bool = True):
        """Setup AI services with Capella AI (Priority 1) and OpenAI fallback."""
        logger.info("🔧 Setting up AI services...")

        # Local variables - will be assigned to instance variables
        embeddings = None
        llm = None

        # Priority 1: Capella AI with OpenAI wrappers
        if use_capella and CAPELLA_API_ENDPOINT and CAPELLA_API_EMBEDDINGS_KEY:
            try:
                endpoint = CAPELLA_API_ENDPOINT
                api_key = CAPELLA_API_EMBEDDINGS_KEY
                model = CAPELLA_API_EMBEDDING_MODEL

                api_base = endpoint if endpoint.endswith('/v1') else f"{endpoint}/v1"

                embeddings = OpenAIEmbeddings(
                    model=model,
                    api_key=api_key,
                    base_url=api_base,
                    check_embedding_ctx_length=False,
                )
                logger.info("✅ Using Capella AI embeddings")
            except Exception as e:
                logger.error(f"❌ Capella AI embeddings failed: {e}")
                embeddings = None

        if use_capella and CAPELLA_API_ENDPOINT and CAPELLA_API_LLM_KEY:
            try:
                endpoint = CAPELLA_API_ENDPOINT
                llm_key = CAPELLA_API_LLM_KEY
                llm_model = CAPELLA_API_LLM_MODEL

                api_base = endpoint if endpoint.endswith('/v1') else f"{endpoint}/v1"

                llm = ChatOpenAI(
                    model=llm_model,
                    base_url=api_base,
                    api_key=llm_key,
                    temperature=temperature,
                )
                # Test the LLM
                test_response = llm.invoke("Hello")
                logger.info("✅ Using Capella AI LLM")
            except Exception as e:
                logger.error(f"❌ Capella AI LLM failed: {e}")
                llm = None

        # Fallback: OpenAI
        if embeddings is None and OPENAI_API_KEY:
            try:
                embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-small",
                    api_key=OPENAI_API_KEY,
                )
                logger.info("✅ Using OpenAI embeddings fallback")
            except Exception as e:
                logger.error(f"⚠️ OpenAI embeddings failed: {e}")

        if llm is None and OPENAI_API_KEY:
            try:
                llm = ChatOpenAI(
                    model="gpt-4o",
                    api_key=OPENAI_API_KEY,
                    temperature=temperature,
                )
                logger.info("✅ Using OpenAI LLM fallback")
            except Exception as e:
                logger.error(f"⚠️ OpenAI LLM failed: {e}")

        if embeddings is None:
            raise ValueError("❌ No embeddings service could be initialized")
        if llm is None:
            raise ValueError("❌ No LLM service could be initialized")

        logger.info("✅ AI services setup completed")
        self.embeddings = embeddings
        self.llm = llm
        return embeddings, llm

    async def setup_environment(self):
        """Setup default environment variables for agent operations."""
        logger.info("✅ Environment variables configured")
        try:
            use_capella = test_capella_connectivity()
            # Test Capella AI connectivity
            if not use_capella:
                logger.error("❌ Capella AI test failed, will use OpenAI fallback")

            # Initialize Agent Catalog v1.0.0
            try:
                logger.info("🔧 Initializing Agent Catalog v1.0.0...")
                self.catalog = Catalog()
                logger.info(f"✅ Agent Catalog initialized (version: {self.catalog.version})")
            except Exception as catalog_error:
                logger.error(f"❌ Failed to initialize Agent Catalog: {catalog_error}")
                self.catalog = None

            # Setup AI services
            try:
                logger.info("🔧 Setting up AI services...")
                self.embeddings, self.llm = self.setup_ai_services(temperature=0.1, use_capella=use_capella)
            except Exception as ai_error:
                logger.error(f"❌ Failed to setup AI services: {ai_error}")
                self.embeddings = None
                self.llm = None

            # Create agent only if all required components are available
            if self.catalog is not None and self.embeddings is not None and self.llm is not None and self.couchbase_client is not None:
                try:
                    logger.info("🤖 Creating LangChain agent...")
                    self.agent_executor = self.create_langchain_agent()
                    logger.info("✅ Agentic HR API Server started successfully!")
                except Exception as agent_error:
                    logger.error(f"❌ Failed to create LangChain agent: {agent_error}")
                    self.agent_executor = None
                try:
                    logger.info("🤖 Creating LangChain Email agent...")
                    self.email_agent_executor = self.create_langchain_email_agent()
                    logger.info("✅ Agentic HR API Server started successfully!")
                except Exception as agent_error:
                    logger.error(f"❌ Failed to create LangChain Email agent: {agent_error}")
                    self.email_agent_executor = None
            else:
                logger.warning("⚠️ Not all required components available, skipping agent creation")
                self.agent_executor = None
                self.email_agent_executor = None
            await self.setup_agentmail()
            # Log final status
            logger.info(f"✅ Setup completed - Agent: {'Ready' if self.agent_executor else 'Not available'}, AI: {'Ready' if self.embeddings and self.llm else 'Not available'}, DB: {'Ready' if self.couchbase_client else 'Not available'}")

        except Exception as e:
            logger.exception(f"❌ Unexpected error during setup: {e}")
            # Don't prevent startup, but log the error
            self.agent_executor = None
            self.embeddings = None
            self.llm = None
            self.couchbase_client = None
            self.catalog = None


    def create_langchain_agent(self):
        """Create LangChain ReAct agent with candidate search tool from Agent Catalog.
        
        Args:
            catalog: Agent Catalog instance (agentc.Catalog v1.0.0)
            embeddings: Embeddings client for vector operations
            llm: Language model for the agent
        """
        try:
            # Setup collection
            self.couchbase_client.setup_collection(DEFAULT_SCOPE, DEFAULT_COLLECTION, clear_existing_data=False)

            # Setup vector search index
            with open("agentcatalog_index.json") as file:
                index_definition = json.load(file)
            logger.info("✅ Loaded vector search index definition")
            self.couchbase_client.setup_vector_search_index(index_definition, DEFAULT_SCOPE)

            # Setup vector store with resume data
            resume_dir = DEFAULT_RESUME_DIR
            self.couchbase_client.setup_vector_store(
                DEFAULT_SCOPE,
                DEFAULT_COLLECTION,
                DEFAULT_INDEX,
                self.embeddings,
                self.llm,
                resume_dir,
            )

            # Load tools from catalog using v1.0.0 API
            # catalog.find() returns a single result when searching by name, or None if not found
            print("\n" + "="*50)
            print("🔍 AGENT CATALOG: Loading tools...")
            print("="*50)

            tools = []

            # Load search_candidates_vector tool
            search_tool_result = self.catalog.find("tool", name="search_candidates_vector")
            if search_tool_result is None:
                raise ValueError("Could not find search_candidates_vector tool in catalog. Run 'agentc index' first.")

            print(f"✅ AGENT CATALOG: Loaded tool '{search_tool_result.meta.name}'")
            print(f"   Description: {search_tool_result.meta.description[:80]}...")
            logger.info(f"✅ Loaded tool from Agent Catalog: {search_tool_result.meta.name}")

            # Create tool wrapper that injects embeddings client
            def search_with_embeddings(job_description: str) -> str:
                return search_tool_result.func(
                    job_description=job_description,
                    num_results=5,
                    embeddings_client=self.embeddings,
                    agent_manager=self
                )

            tools.append(
                Tool(
                    name=search_tool_result.meta.name,
                    description=search_tool_result.meta.description,
                    func=search_with_embeddings,
                )
            )

            # Load analyze_resume tool
            analyze_tool_result = self.catalog.find("tool", name="analyze_resume")
            if analyze_tool_result is not None:
                print(f"✅ AGENT CATALOG: Loaded tool '{analyze_tool_result.meta.name}'")
                print(f"   Description: {analyze_tool_result.meta.description[:80]}...")
                logger.info(f"✅ Loaded tool from Agent Catalog: {analyze_tool_result.meta.name}")

                # Create tool wrapper for resume analysis
                def analyze_with_agent_manager(resume_text: str) -> str:
                    return analyze_tool_result.func(
                        resume_text=resume_text,
                        agent_manager=self
                    )

                tools.append(
                    Tool(
                        name=analyze_tool_result.meta.name,
                        description=analyze_tool_result.meta.description,
                        func=analyze_with_agent_manager,
                    )
                )
            else:
                logger.warning("⚠️ Could not find analyze_resume tool in catalog. It will not be available.")

            # Load prompt from catalog using v1.0.0 API
            # catalog.find() returns a single PromptResult when searching by name
            print("\n🔍 AGENT CATALOG: Loading prompt...")
            prompt_result = self.catalog.find("prompt", name="hr_recruiter_assistant")
            if prompt_result is None:
                raise ValueError("Could not find hr_recruiter_assistant prompt in catalog. Run 'agentc index' first.")

            # In v1.0.0, prompt_result has: content, tools, output, and meta attributes
            print(f"✅ AGENT CATALOG: Loaded prompt '{prompt_result.meta.name}'")
            print(f"   Content length: {len(prompt_result.content)} chars")
            print("="*50 + "\n")
            logger.info(f"✅ Loaded prompt from Agent Catalog: {prompt_result.meta.name}")

            custom_prompt = PromptTemplate(
                template=prompt_result.content.strip(),
                input_variables=["input", "agent_scratchpad"],
                partial_variables={
                    "tools": "\n".join([f"{tool.name}: {tool.description}" for tool in tools]),
                    "tool_names": ", ".join([tool.name for tool in tools]),
                },
            )

            def handle_parsing_error(error) -> str:
                """Custom error handler for parsing errors."""
                logger.warning(f"Parsing error: {error}")
                return """I need to use the correct format. Let me start over:

Thought: I need to search for candidates using the search_candidates_vector tool
Action: search_candidates_vector
Action Input: """

            # Create agent
            agent = create_react_agent(self.llm, tools, custom_prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                handle_parsing_errors=handle_parsing_error,
                max_iterations=5,
                max_execution_time=120,
                early_stopping_method="force",
                return_intermediate_steps=True,
            )

            logger.info("✅ LangChain ReAct agent created successfully")
            return agent_executor

        except Exception as e:
            raise RuntimeError(f"Error creating LangChain agent: {e}")


    def create_langchain_email_agent(self):
        """Create LangChain ReAct agent with email meeting tools.

        Args:
            catalog: Agent Catalog instance (agentc.Catalog v1.0.0)
            embeddings: Embeddings client for vector operations
            llm: Language model for the agent
        """
        try:
            # Setup collection
            self.couchbase_client.setup_collection(DEFAULT_SCOPE, DEFAULT_COLLECTION, clear_existing_data=False)

            # Setup vector search index TODO: Keep for existing email resources to enhance email response ?
            # with open("agentcatalog_index.json") as file:
            #     index_definition = json.load(file)
            # logger.info("✅ Loaded vector search index definition")
            # self.setup_vector_search_index(index_definition, os.environ["CB_SCOPE"])

            # Setup vector store with resume data
            # resume_dir = os.getenv("RESUME_DIR", DEFAULT_RESUME_DIR)
            # self.setup_vector_store(
            #     os.environ["CB_SCOPE"],
            #     os.environ["CB_COLLECTION"],
            #     os.environ["CB_INDEX"],
            #     embeddings,
            #     llm,
            #     resume_dir,
            # )

            # Load tools from catalog using v1.0.0 API
            # catalog.find() returns a single result when searching by name, or None if not found
            print("\n" + "="*50)
            print("🔍 AGENT CATALOG: Loading tool...")
            print("="*50)
            tool_result = self.catalog.find("tool", name="search_hr_availabilities")
            if tool_result is None:
                raise ValueError("Could not find search_hr_availabilities tool in catalog. Run 'agentc index' first.")

            addm = self.catalog.find("tool", name="add_meeting_timeslot")
            seam = self.catalog.find("tool", name="verify_meeting_slot_availability")
            delm = self.catalog.find("tool", name="cancel_meeting_timeslot")

            tools = [
                Tool(
                    name=tool_result.meta.name,
                    description=tool_result.meta.description,
                    func=tool_result.func,
                ),
                Tool(
                    name=addm.meta.name,
                    description=addm.meta.description,
                    func=addm.func,
                ),
                Tool(
                    name=delm.meta.name,
                    description=delm.meta.description,
                    func=delm.func,
                ),
                Tool(
                    name=seam.meta.name,
                    description=seam.meta.description,
                    func=seam.func,
                ),
            ]


            # Load prompt from catalog using v1.0.0 API
            # catalog.find() returns a single PromptResult when searching by name
            print("\n🔍 AGENT CATALOG: Loading prompt...")
            prompt_result = self.catalog.find("prompt", name="hr_schedule_assistant")
            if prompt_result is None:
                raise ValueError("Could not find hr_schedule_assistant prompt in catalog. Run 'agentc index' first.")

            # In v1.0.0, prompt_result has: content, tools, output, and meta attributes
            print(f"✅ AGENT CATALOG: Loaded prompt '{prompt_result.meta.name}'")
            print(f"   Content length: {len(prompt_result.content)} chars")
            print("="*50 + "\n")
            logger.info(f"✅ Loaded prompt from Agent Catalog: {prompt_result.meta.name}")

            # custom_prompt = PromptTemplate(
            #     template=prompt_result.content.strip(),
            #     input_variables=["input", "agent_scratchpad"],
            #     partial_variables={
            #         "tools": "\n".join([f"{tool.name}: {tool.description}" for tool in tools]),
            #         "tool_names": ", ".join([tool.name for tool in tools]),
            #     },
            # )

            # Create proper prompt template for tool calling agent
            custom_prompt = ChatPromptTemplate.from_messages([
                    ("system", prompt_result.content.strip()),
                    ("human", "{thread}"),
                    MessagesPlaceholder("agent_scratchpad"),
                ])


            def handle_parsing_error(error) -> str:
                """Custom error handler for parsing errors."""
                logger.warning(f"Parsing error: {error}")
                return """I need to use the correct format. Let me start over:

Thought: I need answer the email thread to setup a meeting. I cand find meeting availabilities with search_hr_availabilities
Action: search_hr_availabilities
Action Input: """

            # Create agent
            agent = create_tool_calling_agent(self.llm, tools, custom_prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                handle_parsing_errors=handle_parsing_error,
                max_iterations=5,
                max_execution_time=120,
                early_stopping_method="force",
                return_intermediate_steps=True,
            )

            logger.info("✅ LangChain ReAct agent created successfully")
            return agent_executor

        except Exception as e:
            raise RuntimeError(f"Error creating LangChain agent: {e}")


    # Initialize AgentMail client only when needed and with proper error handling
    def get_agentmail_client(self):
        """Get AgentMail client with proper initialization."""
        api_key = AGENTMAIL_API_KEY
        if not api_key:
            raise ValueError("AGENTMAIL_API_KEY environment variable is required for AgentMail functionality")
        return AgentMail(api_key=api_key)

    async def setup_agentmail(self):
        """Create inbox and webhook with idempotency."""
        print("Setting up AgentMail infrastructure...")

        # Get AgentMail client
        client = self.get_agentmail_client()
        inbox_id = f"{INBOX_USERNAME}@agentmail.to"
        # Create inbox (or get existing one)
        try:
            inbox = client.inboxes.get(inbox_id)
            print(f"✓ Inbox created: {inbox.inbox_id}")
        except Exception as e:
            if "already exists" in str(e).lower():
                inbox_id = f"{INBOX_USERNAME}@agentmail.to"
                class SimpleInbox:
                    def __init__(self, inbox_id):
                        self.inbox_id = inbox_id
                inbox = SimpleInbox(inbox_id)
                print(f"✓ Using existing inbox: {inbox.inbox_id}")
            else:
                raise

        # Start ngrok tunnel
        if SERVER_URL == "":
            listener = await ngrok.forward(PORT, domain=WEBHOOK_DOMAIN, authtoken_from_env=True)
            listener_url = listener.url()
        else:
            listener_url = SERVER_URL
        # Create webhook (or get existing one)
        try:
            webhook = client.webhooks.create(
                url=f"{listener_url}/webhook/agentmail",
                event_types=["message.received"],
                inbox_ids=[inbox.inbox_id],
                client_id=f"{INBOX_USERNAME}-webhook"
            )
            print(f"✓ Webhook created")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"Webhook already exists")
            else:
                raise


        print(f"\n✓ Setup complete!")
        print(f"Inbox: {inbox.inbox_id}")
        print(f"Webhook: {listener_url}/webhook/agentmail\n")

        return inbox, listener

    def generate_reply(sender_name, subject):
        """Generate auto-reply message using a template."""
        return (
            f"Hi {sender_name},\n\n"
            f"Thank you for your email! I've received your message and will get back to you within 24 hours.\n\n"
            f"If your matter is urgent, please reply with \"URGENT\" in the subject line.\n\n"
            f"Best regards,\n"
            f"Auto-Reply Agent"
        )

    def generate_openai_reply(sender_name, subject, message_content, application_data, thread_context=""):
        """Generate intelligent auto-reply using OpenAI based on application and thread context."""

        # Prepare context for OpenAI
        context_parts = []

        # Add application context if available
        if application_data:
            context_parts.append(f"Applicant: {application_data.get('full_name', 'Unknown')}")
            context_parts.append(f"Position: {application_data.get('position', 'Unknown')}")
            context_parts.append(f"Company: {application_data.get('company_name', 'Unknown')}")
            context_parts.append(f"Application Status: {application_data.get('status', 'Unknown')}")

        # Add email thread context
        if thread_context:
            context_parts.append(f"Previous correspondence: {thread_context}")

        # Create system prompt for OpenAI
        system_prompt = f"""You are a professional HR assistant helping with interview scheduling and candidate communication.
    You have access to the following context about this email exchange:

    {chr(10).join(context_parts)}

    Generate a professional, helpful, and contextually appropriate reply to this email.
    The reply should:
    - Be warm and professional in tone
    - Acknowledge the specific content of their message
    - Reference their application/interview process if relevant
    - Provide clear next steps or ask for clarification when needed
    - Be concise but comprehensive
    - Never promise specific meeting times without proper scheduling process

    Keep the reply under 200 words. Return only the message"""

        # Prepare user message with sender and original email details
        user_message = f"Sender: {sender_name}\nSubject: {subject}\nMessage: {message_content}\n\nPlease generate an appropriate reply."

        msgs = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
        ]
        try:
            # Call OpenAI API
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages= msgs,
                max_tokens=300,
                temperature=0.7
            )

            # Extract the generated reply
            reply = response.choices[0].message.content.strip()
            return reply

        except Exception as e:
            print(f"Error generating OpenAI reply: {e}")
            # Fallback to simple template if OpenAI fails
            return (
                f"Hi {sender_name},\n\n"
                f"Thank you for your email! I've received your message regarding '{subject}' and will get back to you within 24 hours.\n\n"
                f"If your matter is urgent, please reply with \"URGENT\" in the subject line.\n\n"
                f"Best regards,\n"
                f"Auto-Reply Agent"
            )

    def process_and_reply(self, email_agent_executor, message_id, inbox_id, from_field, subject, message, application, application_key):
        """Process incoming message and send reply in background."""
        # Extract sender email and name
        if '<' in from_field and '>' in from_field:
            sender_email = from_field.split('<')[1].split('>')[0].strip()
            sender_name = from_field.split('<')[0].strip()
            if not sender_name or ',' in sender_name:
                sender_name = sender_email.split('@')[0].title()
        else:
            sender_email = from_field.strip()
            sender_name = sender_email.split('@')[0].title() if '@' in sender_email else 'Friend'

        # Log incoming email
        logger.info(f"Processing email from {sender_email}: {subject}\n")
        logger.info(f"Processing message {message}")

        # Generate and send auto-reply
        try:
            # Extract message content for OpenAI
            # message_content = ""
            # if message and isinstance(message, dict):
            #     message_content = message.get('text_content', message.get('body', ''))
            #     if not message_content:
            #         # Try to get from different possible fields
            #         content = message.get('content', '')
            #         if isinstance(content, str):
            #             message_content = content
            #         elif isinstance(content, dict):
            #             message_content = content.get('text', '') or content.get('html', '')
            # else:
            #     message_content = message

            # Use OpenAI to generate intelligent reply
            # reply_text = generate_openai_reply(
            #     sender_name=sender_name,
            #     subject=subject,
            #     message_content=message_content,
            #     application_data=application,
            #     thread_context=""
            # )

            

            # Run the agent
            
            response = email_agent_executor.invoke({"meeting_id": application_key, "agent_scratchpad":"","today": datetime.today().strftime('%Y-%m-%d'),"thread": message.get('text').strip()})

            # # Extract the agent's response
            agent_output = response.get("output", "Could not generate anwser")
            intermediate_steps = response.get("intermediate_steps", [])


            # Get AgentMail client
            client = self.get_agentmail_client()

            # Send reply
            client.inboxes.messages.reply(
                inbox_id=inbox_id,
                message_id=message_id,
                to=[sender_email],
                text=agent_output
            )
            print(f"Auto-reply sent to {sender_email}\n")
        except Exception as e:
            print(f"Error: {e}\n")

    def render_email_template(template_content, template_vars):
        """Render Jinja2 template with variables."""
        template = Template(template_content)
        return template.render(**template_vars)

    def close(self):
        self.agent_executor = None
        self.embeddings = None
        self.llm = None
        self.couchbase_client = None
        self.catalog = None
