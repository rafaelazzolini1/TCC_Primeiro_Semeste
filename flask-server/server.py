
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS

import nacl.secret
import nacl.utils
from nacl.encoding import Base64Encoder

from langchain_community.chat_models import ChatOpenAI
from langchain.schema import HumanMessage
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_community.llms import OpenAI
from langchain.agents import AgentExecutor
from langchain.agents.agent_types import AgentType

from langchain.chains import create_sql_query_chain
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotPromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
    SystemMessagePromptTemplate,
)

from langchain.agents import tool
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser


app = Flask(__name__)#, static_folder='../client/build', template_folder='../client/build'

CORS(app)

# ============ LibSodiumStart ============ #

# keyFront = Base64Encoder.decode(key_base64)
# encrypted_message_base64 = '4+DkFy4IqOAO5elqm/zamFbfXLJVZc7Td0RfFgRhYw+q4/lDXFochLo6ZCQwgglBbq/63pUSPEaFruvJWU5VCiRFJBjJTOE=' #AQUI SERIA O TOKEN JÁ CRIPTOGRAFADO
# encrypted_message = Base64Encoder.decode(encrypted_message_base64)

# nonce = encrypted_message[:nacl.secret.SecretBox.NONCE_SIZE]
# encrypted = encrypted_message[nacl.secret.SecretBox.NONCE_SIZE:]

# box = nacl.secret.SecretBox(key)

# decrypted_message = box.decrypt(encrypted, nonce)

# ============ LibSodiumEnd ============ #

database_uri = ""  ## ======== Caminho SQL SERVER local ========= ## ===============================================================
sql_db = SQLDatabase.from_uri(database_uri)

    #result = sql_db.run('SELECT TOP 10 * FROM ARTIST')

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0## ======== Chave API Open AI ========= ## ===============================================================
)

# agent_executor = create_sql_agent(llm, db=sql_db, agent_type="tool-calling", verbose=True)

@tool
def separaPalavras(texto: str) -> dict:
    """Returns a dict of words from a text string"""
    texto = texto.replace(',', '')
    split = texto.split()

    return split

tools = [separaPalavras]

promptValid = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Você é um agente inteligente cuja função é interpretar se uma informação é bloqueada ou permitida.\
             Você deve verificar se a frase contida em input se relaciona de alguma forma com temas que envolvam salário, pagamentos, dinheiro, raça, religião, orientação sexual\
            Se considerar que existe alguma relação, retorne a palavra 'Bloqueado'\
            Caso contrário apenas retorne a palavra 'Permitido'\
            ",
        ),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

llm_with_tools = llm.bind_tools(tools)

agentValid = (
    {
        "input": lambda x: x["input"],
        "agent_scratchpad": lambda x: format_to_openai_tool_messages(
            x["intermediate_steps"]
        ),
    }
    | promptValid
    | llm_with_tools
    | OpenAIToolsAgentOutputParser()
)

agent_executor = AgentExecutor(agent=agentValid, tools=tools, verbose=True)

examples = [
    {"input": "Quanto é o saldo de salário do Usuário1?",
     "query": "SELECT (Salario/30) * DAY([DataDemissao]) AS SaldoSalario FROM [Funcionario] WHERE [Nome] = 'Usuário1'"
    },
    {"input": "Qual o valor do décimo terceiro proporcional do funcionário Carlos Almeida?",
     "query": "select (Salario/12) * DATEDIFF(month, cast(dateadd(yy, datediff(yy, 0, GETDATE()), 0) as date), cast(getdate() as date)) AS DateDiff from Funcionario where nome = 'Carlos Almeida'"
    },
    {"input": "Qual o valor do FGTS total do funcionário João Gomes?",
     "query": "select (Salario * 0.08) * DATEDIFF(month, DataAdmissao, cast(getdate() as date)) AS FGTS from Funcionario where nome = 'João Gomes'; "
    },
    {"input": "Qual o valor da multa de 40% do funcionário João Gomes?",
     "query": "select 0.4 * (Salario * 0.08) * DATEDIFF(month, DataAdmissao, cast(getdate() as date)) AS FGTS from Funcionario where nome = 'João Gomes'; "
    },
    {"input": "Qual o valor da folha de pagamento total da empresa?",
     "query": "select sum(Salario) as FolhaPagamento from Funcionario Where DataDemissao is Null"
    },
    {"input": "Qual a politica de ferias da empresa?",
     "query": "select PoliticaDescricao as Politica from Politicas Where PoliticaNome like '%Ferias%'" 
    }
]

example_selector = SemanticSimilarityExampleSelector.from_examples(
    examples,
    FAISS,
    k=5,
    input_keys=["input"],
)

system_prefix = """Você é um Agent desenvolvido para interagir com uma base de dados SQL.
Através de uma pergunta feita num input, crie uma query SQL SERVER sintaticamente correta para executar, então observe os resultados da query e retorne a resposta.
Se o usuário não especificar a quantidade de exemplos de retorno, sempre limite sua query a no máximo {top_k} resultados.
Você pode ordenar os resultados por uma coluna relevante para retornar os exemplos mais interessantes da base de dados.
Nunca faça uma busca por todas as colunas de uma tabela específica, apenas busque pelas colunas mais relevantes de acordo com a pergunta.
Você tem acesso a ferramentas para interagir com a base de dados.
Apenas use as ferramentas fornecidas. Apenas use as informações devolvidas pelas ferramentas para construir sua resposta final.
Você DEVE verificar duas vezes sua query antes de executá-la. Se houver algum erro ao executar a query, reescreva a query e tente novamente.

NÃO faça nenhum comando de DML (INSERT, UPDATE, DELETE, DROP etc.) na base de dados.

Se a pergunta não parecer relacionada à base de dados, apenas retorne "Eu não sei" como resposta.

Aqui estão alguns exemplos de inputs de usuário e suas querys correspondentes:"""

few_shot_prompt = FewShotPromptTemplate(
    example_selector=example_selector,
    example_prompt=PromptTemplate.from_template(
        "User input: {input}\nSQL query: {query}"
    ),
    input_variables=["input", "top_k"],
    prefix=system_prefix,
    suffix="",
)

full_prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate(prompt=few_shot_prompt),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)

agent = create_sql_agent(
    llm=llm,
    db=sql_db,
    prompt=full_prompt,
    verbose=True,
    agent_type="tool-calling",
)

@app.route("/members")
def members():
    return {"members": ["member1", "member2", "member3"]}

@app.route("/cryptokey")
def retornaChave():
    chave = {'chave': 'q9egeDk+L1t2C8pgH/9rzE/ezPflr3cx6JLujZSiaX8='}
    return jsonify({'chave': chave})

@app.after_request
def remove_server_header(response):
    response.headers.pop('Server', None)  # Remove o cabeçalho Server
    return response



@app.route('/api/dados', methods=['POST'])
def receber_dados():
    dados = request.json
    print(dados)

    nome = dados.get('nome')
    print(nome)

    token = dados.get('token')
    print(token)

    keyFront = Base64Encoder.decode('q9egeDk+L1t2C8pgH/9rzE/ezPflr3cx6JLujZSiaX8=')
    encrypted_message_base64 = token
    encrypted_message = Base64Encoder.decode(encrypted_message_base64)

    nonce = encrypted_message[:nacl.secret.SecretBox.NONCE_SIZE]
    encrypted = encrypted_message[nacl.secret.SecretBox.NONCE_SIZE:]

    box = nacl.secret.SecretBox(keyFront)

    decrypted_message = box.decrypt(encrypted, nonce)



    if decrypted_message.decode() == 'funcionario':
        resultadoValidacao = agent_executor.invoke({"input": nome})
        validacao = resultadoValidacao['output']

        if validacao == 'Bloqueado':
            result = {'output': 'Não posso fornecer essa informação.'}

        else:
            result = agent.invoke({"input": nome})

    else:
        result = agent.invoke({"input": nome}
                              
)
    print(result)
    response = make_response(jsonify({'result': result}))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none';"
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

    #return jsonify({'result': result})

if __name__ == "__main__":
    app.run(debug=True)

    

