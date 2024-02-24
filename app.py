from flasgger import Swagger
from flask import Flask, jsonify

app = Flask(__name__)
swagger = Swagger(app)


@app.route("/hello", methods=["GET"])
def hello():
    """
    This endpoint returns a hello message.
    ---
    responses:
      200:
        description: A hello message
        schema:
          type: object
          properties:
            message:
              type: string
    """
    return jsonify({"message": "Hello, World!"})


if __name__ == "__main__":
    app.run(debug=True)
