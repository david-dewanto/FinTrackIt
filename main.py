from fastapi import FastAPI, Depends
from routers import secure, public
from auth import get_user

description = """
## Secure Endpoints
Merupakan API Endpoints yang baru dapat dipanggil **apabila sudah melakukan API Authentication** \n
**API Key (Masukkan ke Field Authorize) : e54d4431-5dab-474e-b71a-0db1fcb9e659**

* **Get Historical Prices** (Mengembalikan Harga Saham Menggunakan Yahoo Finance).
* **Test Route** (Mencoba API Endpoint Private (_Hanya Mengembalikkan Message "OK"_)).



## Public Endpoints
Merupakan API Endpoints yang dapat dipanggil **tanpa melakukan API Authentication**

* **Test Route** (Mencoba API Endpoint Public (_Hanya Mengembalikkan Message "OK"_)).
"""

tags_metadata = [
    {
        "name": "Historical Stock Price",
        "description": "Mencoba Endpoint Private, Mengembalikkan Harga Saham BBCA dan TLKM dari 11/11/2024 sampai 22/11/2024",
    },
    {
        "name": "Private Test Route",
        "description": "Mencoba Endpoint Private, Mengembalikkan Pesan 'OK' apabila Berhasil",
    },
    {
        "name": "Public Test Route",
        "description": "Mencoba Endpoint Public, Mengembalikkan Pesan 'OK' apabila Berhasil",
    }
]


app = FastAPI(
    openapi_tags=tags_metadata,
    title="Tugas TST - 18222027 - David Dewanto",
    description=description,
    version="1.0.0",
)


app.include_router(
    public.router,
    prefix="/api/v1/public"
)
app.include_router(
    secure.router,
    prefix="/api/v1/secure",
    dependencies=[Depends(get_user)]
)