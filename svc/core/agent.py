import os
import logging
import json
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from svc.core.config import DEFAULT_RESUME_DIR
from svc.core.db import CouchbaseClient, test_capella_connectivity
from agentc import Catalog

logger = logging.getLogger("uvicorn.error" )


class AgentManager:
    """Manager class for AI services and agent components."""

    def __init__(self, couchbase_client):
        self.agent_executor = None
        self.embeddings = None
        self.llm = None
        self.couchbase_client = couchbase_client
        self.catalog = None

    def setup_ai_services(self, temperature: float = 0.0, use_capella: bool = True):
        """Setup AI services with Capella AI (Priority 1) and OpenAI fallback."""
        logger.info("🔧 Setting up AI services...")

        # Local variables - will be assigned to instance variables
        embeddings = None
        llm = None

        # Priority 1: Capella AI with OpenAI wrappers
        if use_capella and os.getenv("CAPELLA_API_ENDPOINT") and os.getenv("CAPELLA_API_EMBEDDINGS_KEY"):
            try:
                endpoint = os.getenv("CAPELLA_API_ENDPOINT")
                api_key = os.getenv("CAPELLA_API_EMBEDDINGS_KEY")
                model = os.getenv("CAPELLA_API_EMBEDDING_MODEL")

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

        if use_capella and os.getenv("CAPELLA_API_ENDPOINT") and os.getenv("CAPELLA_API_LLM_KEY"):
            try:
                endpoint = os.getenv("CAPELLA_API_ENDPOINT")
                llm_key = os.getenv("CAPELLA_API_LLM_KEY")
                llm_model = os.getenv("CAPELLA_API_LLM_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B")

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
        if embeddings is None and os.getenv("OPENAI_API_KEY"):
            try:
                embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-small",
                    api_key=os.getenv("OPENAI_API_KEY"),
                )
                logger.info("✅ Using OpenAI embeddings fallback")
            except Exception as e:
                logger.error(f"⚠️ OpenAI embeddings failed: {e}")

        if llm is None and os.getenv("OPENAI_API_KEY"):
            try:
                llm = ChatOpenAI(
                    model="gpt-4o",
                    api_key=os.getenv("OPENAI_API_KEY"),
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

    def setup_environment(self):
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
            else:
                logger.warning("⚠️ Not all required components available, skipping agent creation")
                self.agent_executor = None

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
            self.couchbase_client.setup_collection(os.environ["CB_SCOPE"], os.environ["CB_COLLECTION"], clear_existing_data=False)

            # Setup vector search index
            with open("agentcatalog_index.json") as file:
                index_definition = json.load(file)
            logger.info("✅ Loaded vector search index definition")
            self.couchbase_client.setup_vector_search_index(index_definition, os.environ["CB_SCOPE"])

            # Setup vector store with resume data
            resume_dir = DEFAULT_RESUME_DIR
            self.couchbase_client.setup_vector_store(
                os.environ["CB_SCOPE"],
                os.environ["CB_COLLECTION"],
                os.environ["CB_INDEX"],
                self.embeddings,
                self.llm,
                resume_dir,
            )

            # Load tools from catalog using v1.0.0 API
            # catalog.find() returns a single result when searching by name, or None if not found
            print("\n" + "="*50)
            print("🔍 AGENT CATALOG: Loading tool...")
            print("="*50)
            tool_result = self.catalog.find("tool", name="search_candidates_vector")
            if tool_result is None:
                raise ValueError("Could not find search_candidates_vector tool in catalog. Run 'agentc index' first.")

            # In v1.0.0, tool_result has: func, meta, and input attributes
            print(f"✅ AGENT CATALOG: Loaded tool '{tool_result.meta.name}'")
            print(f"   Description: {tool_result.meta.description[:80]}...")
            logger.info(f"✅ Loaded tool from Agent Catalog: {tool_result.meta.name}")

            # Create tool wrapper that injects embeddings client
            def search_with_embeddings(job_description: str) -> str:
                return tool_result.func(
                    job_description=job_description,
                    num_results=5,
                    embeddings_client=self.embeddings,
                    agent_manager=self
                )

            tools = [
                Tool(
                    name=tool_result.meta.name,
                    description=tool_result.meta.description,
                    func=search_with_embeddings,
                ),
            ]

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


    def close(self):
        self.agent_executor = None
        self.embeddings = None
        self.llm = None
        self.couchbase_client = None
        self.catalog = None


