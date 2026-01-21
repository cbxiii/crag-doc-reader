from pydantic_ai import Agent
import dotenv

dotenv.load_dotenv()

agent = Agent('openai:gpt-4o-mini')

res = agent.run_sync("What is the meaning of life?")

print(res.output)