# Descargador Masivo de TikTok (n8n + Docker + yt-dlp)

Microservicio en Python (Flask) orquestado por n8n para descargar de manera masiva y asíncrona videos de perfiles de TikTok. Este proyecto demuestra habilidades de automatización e integración de microservicios mediante contenedores, destacando competencias técnicas en el desarrollo de software backend estructurado.

## Arquitectura

El sistema separa la orquestación de la ejecución, utilizando una red interna de Docker para la comunicación:

1. **Orquestador (n8n):** Un formulario web recibe la URL del perfil e inicia un flujo de trabajo que gestiona el ciclo de vida de la petición.
2. **Microservicio (Flask + yt-dlp):** Procesa la descarga en segundo plano y expone *endpoints* de control (`/download`, `/status/<job_id>`, `/health`).

```text
[Formulario n8n] -> POST /download -> [Microservicio Flask] -> Inicia yt-dlp + ffmpeg
       |                                       |
       +<-- GET /status/<job_id> (cada 30s) <--+ 
       |                                       v
[Condicional IF]                         Guarda en ./downloads/USUARIO/
```

## Características Principales

* **Patrón de Polling Asíncrono:** n8n dispara la descarga mediante un nodo HTTP Request (`POST`), espera 5 segundos con un nodo *Wait*, y consulta el estado del trabajo (`GET`) iterando en un ciclo condicional (*If*) hasta que el proceso finaliza.
* **Descargas Idempotentes:** Utiliza un archivo `archive.txt` para registrar los IDs de los videos descargados, permitiendo reanudar procesos o actualizar perfiles sin duplicar archivos.
* **Máxima Calidad:** Integra `ffmpeg` y `yt-dlp` configurados (`-f "bv*+ba/b"`) para solicitar y fusionar de manera automática la mejor pista de video y audio disponible.
* **Tolerancia a Bloqueos:** Soporta el uso de un archivo `cookies.txt` en modo solo lectura para autenticar la sesión y evadir las restricciones de extracción de datos de la plataforma.
* **Protección de Concurrencia:** El microservicio bloquea múltiples peticiones simultáneas, devolviendo un error HTTP 409 si ya existe un trabajo en curso.

## Tecnologías Utilizadas

* **Python 3.12** / **Flask:** Desarrollo de la API REST.
* **n8n:** Orquestación de flujos de trabajo.
* **Docker & Docker Compose:** Contenerización y gestión de redes.
* **yt-dlp & ffmpeg:** Extracción y procesamiento multimedia.

## Estructura del Proyecto

```text
/
├── docker-compose.yml       # Definición del contenedor del microservicio
├── pofiwd.json              # Flujo exportado de n8n
├── downloader/
│   ├── app.py               # Lógica del microservicio Flask
│   ├── Dockerfile           # Receta de la imagen con ffmpeg y yt-dlp
│   └── requirements.txt     # Dependencias de Python
├── downloads/               # Volumen de salida para archivos .mp4
└── config/                  # Archivos de configuración (ej. cookies.txt)
```

## Despliegue e Instalación

1. **Construir el microservicio:** Ejecuta la compilación de la imagen de Docker, la cual instalará automáticamente las dependencias (Python, `ffmpeg`, `yt-dlp`).
   ```bash
   docker compose up -d --build downloader
   ```
2. **Importar el flujo:** En la interfaz de n8n, importa el archivo `pofiwd.json`. Este flujo incluye el disparador *On form submission*, las peticiones HTTP y el ciclo de consulta.
3. **Uso:** Accede a la URL de producción del formulario de n8n, ingresa un enlace (ej. `https://www.tiktok.com/@usuario`) y verifica el progreso en los *logs* del contenedor.

**Aviso legal**: Este proyecto fue creado con fines de aprendizaje y automatización personal. Se exige un uso ético y responsable de la herramienta, limitando las descargas exclusivamente a contenido propio o a perfiles de los cuales se tenga permiso explícito por parte del creador.