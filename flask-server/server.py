# from flask import Flask, send_from_directory, render_template
# from langchain.chat_models import ChatOpenAI
# from langchain.schema import HumanMessage
# from flask_sqlalchemy import SQLAlchemy

# app = Flask(__name__, static_folder='../client/build/static', template_folder='../client/build')

# db = SQLAlchemy()

# class Data(db.Model): 
#     id  = db.Column(db.Integer, primary_key = True)
#     content = db.Column(db.String)

# @app.route("/members")
# def members():
#     return {"members": ["member2", "member2", "member3"]}

# @app.route("/query_open_ai", methods = ['POST'])
# def query_open_ai():
#     llm = ChatOpenAI(temperature=0, model_name='gpt-3.5-turbo', openai_api_key='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')

#     print(llm([HumanMessage(content='What is 2+2')]))

#     return {
#         'statusCode': 500,
#         'body': 'TODO'
#     }

# if __name__ == "__main__":
#     app.run(debug=True)


from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage

# from flask_sqlalchemy import SQLAlchemy

from langchain.agents import create_sql_agent
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.sql_database import SQLDatabase
from langchain.llms.openai import OpenAI
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

app = Flask(__name__)#, static_folder='../client/build', template_folder='../client/build'

CORS(app)

database_uri = ""
sql_db = SQLDatabase.from_uri(database_uri)

    #result = sql_db.run('SELECT TOP 10 * FROM ARTIST')

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key = "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")
# agent_executor = create_sql_agent(llm, db=sql_db, agent_type="tool-calling", verbose=True)

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
    }
]

example_selector = SemanticSimilarityExampleSelector.from_examples(
    examples,
    OpenAIEmbeddings(openai_api_key=""),
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

# db = SQLAlchemy()

# class Data(db.Model): 
#     id = db.Column(db.Integer, primary_key=True)
#     content = db.Column(db.String)

@app.route("/members")
def members():
    return {"members": ["member1", "member2", "member3"]}

@app.route('/api/dados', methods=['POST'])
def receber_dados():
    dados = request.json  # Obtém os dados JSON enviados pelo React
    print(dados)  # Processa os dados conforme necessário
    nome = dados.get('nome')
    print(nome)

    result = agent.invoke({
    "input": nome}
)

    return jsonify({'result': result})

# @app.route("/query_open_ai", methods=['POST'])
# def query_open_ai():
#     llm = ChatOpenAI(temperature=0, model_name='gpt-3.5-turbo', openai_api_key='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')

#     print(llm([HumanMessage(content='What is 2+2')]))

#     return {
#         'statusCode': 500,
#         'body': 'TODO'
#     }

# @app.route('/')
# def index():
#     return render_template('index.html')

# @app.route('/<path:path>')
# def serve_static(path):
#     return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    app.run(debug=True)

