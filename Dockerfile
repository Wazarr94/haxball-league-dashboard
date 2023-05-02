FROM python:3.9.6
EXPOSE 8501
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip3 install -r requirements.txt
COPY . .
RUN prisma generate dev
CMD streamlit run Home.py