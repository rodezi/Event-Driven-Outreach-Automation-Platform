"""
Queries de búsqueda organizadas por ciudad.
Cada query apunta a una zona/colonia específica para maximizar cobertura
(Google Maps limita ~120-200 resultados por búsqueda).

Uso en scraper:
    python scraper.py --city CDMX
    python scraper.py --city QUERETARO
    python scraper.py --list-cities
"""

CITIES: dict[str, list[str]] = {

    # ── CDMX — 16 alcaldías ────────────────────────────────────────────────────
    "CDMX": [
        # Miguel Hidalgo
        "inmobiliaria Polanco Ciudad de México",
        "inmobiliaria Lomas de Chapultepec",
        "inmobiliaria Las Lomas CDMX",
        "inmobiliaria Anzures CDMX",
        "inmobiliaria San Miguel Chapultepec",
        "inmobiliaria Tacuba CDMX",
        "inmobiliaria Popotla CDMX",

        # Cuauhtémoc
        "inmobiliaria Roma Norte Ciudad de México",
        "inmobiliaria Roma Sur CDMX",
        "inmobiliaria Condesa CDMX",
        "inmobiliaria Hipódromo CDMX",
        "inmobiliaria Centro Histórico CDMX",
        "inmobiliaria Doctores CDMX",
        "inmobiliaria Juárez CDMX",
        "inmobiliaria Guerrero CDMX",
        "inmobiliaria Tlatelolco CDMX",
        "inmobiliaria Santa María la Ribera",
        "inmobiliaria Tepito CDMX",

        # Benito Juárez
        "inmobiliaria Del Valle CDMX",
        "inmobiliaria Narvarte CDMX",
        "inmobiliaria Nápoles CDMX",
        "inmobiliaria Portales CDMX",
        "inmobiliaria Insurgentes CDMX",
        "inmobiliaria Nochebuena CDMX",
        "inmobiliaria Mixcoac CDMX",

        # Álvaro Obregón
        "inmobiliaria Santa Fe Ciudad de México",
        "inmobiliaria San Ángel CDMX",
        "inmobiliaria Altavista CDMX",
        "inmobiliaria Olivar de los Padres",
        "inmobiliaria Tizapán San Ángel",
        "inmobiliaria Presidentes Ejidales",

        # Coyoacán
        "inmobiliaria Coyoacán Ciudad de México",
        "inmobiliaria Pedregal de San Ángel",
        "inmobiliaria Villa Coyoacán",
        "inmobiliaria Churubusco CDMX",
        "inmobiliaria Copilco CDMX",
        "inmobiliaria El Carmen Coyoacán",

        # Tlalpan
        "inmobiliaria Tlalpan Ciudad de México",
        "inmobiliaria Pedregal de Carrasco",
        "inmobiliaria Isidro Fabela CDMX",
        "inmobiliaria Fuentes del Pedregal",
        "inmobiliaria Club de Golf México",

        # Iztapalapa
        "inmobiliaria Iztapalapa Ciudad de México",
        "inmobiliaria Ermita Iztapalapa",
        "inmobiliaria Santa Catarina Iztapalapa",
        "inmobiliaria San Lorenzo Tezonco",
        "inmobiliaria Cerro de la Estrella",
        "inmobiliaria Agrícola Pantitlán",
        "inmobiliaria Culhuacán CDMX",

        # Gustavo A. Madero
        "inmobiliaria Lindavista CDMX",
        "inmobiliaria Vallejo CDMX",
        "inmobiliaria Tepeyac CDMX",
        "inmobiliaria La Villa CDMX",
        "inmobiliaria Martín Carrera CDMX",
        "inmobiliaria Gustavo A Madero",

        # Azcapotzalco
        "inmobiliaria Azcapotzalco Ciudad de México",
        "inmobiliaria Clavería CDMX",
        "inmobiliaria Del Gas CDMX",
        "inmobiliaria Nueva Santa María CDMX",
        "inmobiliaria San Marcos Azcapotzalco",

        # Venustiano Carranza
        "inmobiliaria Venustiano Carranza CDMX",
        "inmobiliaria Jardín Balbuena",
        "inmobiliaria Peñón de los Baños",
        "inmobiliaria Merced CDMX",
        "inmobiliaria Aeropuerto CDMX",

        # Iztacalco
        "inmobiliaria Iztacalco Ciudad de México",
        "inmobiliaria Agrícola Oriental CDMX",
        "inmobiliaria Pantitlán CDMX",

        # Cuajimalpa
        "inmobiliaria Cuajimalpa Ciudad de México",
        "inmobiliaria Santa Fe Cuajimalpa",
        "inmobiliaria Contadero CDMX",

        # Xochimilco
        "inmobiliaria Xochimilco Ciudad de México",
        "inmobiliaria San Gregorio Atlapulco",

        # Tláhuac
        "inmobiliaria Tláhuac Ciudad de México",
        "inmobiliaria San Francisco Tlaltenco",

        # La Magdalena Contreras
        "inmobiliaria La Magdalena Contreras",
        "inmobiliaria Pedregal de San Nicolás",

        # Milpa Alta
        "inmobiliaria Milpa Alta Ciudad de México",
    ],

    # ── Querétaro ──────────────────────────────────────────────────────────────
    "QUERETARO": [
        "inmobiliaria Querétaro centro",
        "inmobiliaria Juriquilla Querétaro",
        "inmobiliaria El Marqués Querétaro",
        "inmobiliaria Corregidora Querétaro",
        "inmobiliaria El Refugio Querétaro",
        "inmobiliaria Cumbres Querétaro",
        "inmobiliaria Zibatá Querétaro",
        "inmobiliaria Constituyentes Querétaro",
        "inmobiliaria Hércules Querétaro",
        "inmobiliaria San Juan del Río Querétaro",
    ],

    # ── Guadalajara ────────────────────────────────────────────────────────────
    "GUADALAJARA": [
        "inmobiliaria Guadalajara centro",
        "inmobiliaria Zapopan Jalisco",
        "inmobiliaria Providencia Guadalajara",
        "inmobiliaria Chapalita Guadalajara",
        "inmobiliaria Ciudad Granja Zapopan",
        "inmobiliaria Puerta de Hierro Zapopan",
        "inmobiliaria Tlaquepaque Jalisco",
        "inmobiliaria Tonalá Jalisco",
        "inmobiliaria Tlajomulco Jalisco",
        "inmobiliaria Bugambilias Zapopan",
        "inmobiliaria Santa Anita Guadalajara",
        "inmobiliaria Colomos Guadalajara",
    ],

    # ── Monterrey ──────────────────────────────────────────────────────────────
    "MONTERREY": [
        "inmobiliaria Monterrey centro",
        "inmobiliaria San Pedro Garza García",
        "inmobiliaria Santa Catarina Nuevo León",
        "inmobiliaria San Nicolás de los Garza",
        "inmobiliaria Apodaca Nuevo León",
        "inmobiliaria Cumbres Monterrey",
        "inmobiliaria Lomas de San Francisco Monterrey",
        "inmobiliaria Valle Poniente Monterrey",
        "inmobiliaria García Nuevo León",
        "inmobiliaria Escobedo Nuevo León",
    ],

    # ── Los Cabos ──────────────────────────────────────────────────────────────
    "LOS_CABOS": [
        "inmobiliaria Los Cabos",
        "inmobiliaria Cabo San Lucas",
        "inmobiliaria San José del Cabo",
        "inmobiliaria Pedregal Cabo San Lucas",
        "inmobiliaria El Tezal Los Cabos",
        "inmobiliaria Palmilla Los Cabos",
        "inmobiliaria Corridor Los Cabos",
    ],

    # ── Cancún ────────────────────────────────────────────────────────────────
    "CANCUN": [
        "inmobiliaria Cancún zona hotelera",
        "inmobiliaria Cancún centro",
        "inmobiliaria Cancún Puerto Morelos",
        "inmobiliaria Playa del Carmen",
        "inmobiliaria Tulum Quintana Roo",
        "inmobiliaria Solidaridad Playa del Carmen",
        "inmobiliaria Isla Mujeres",
        "inmobiliaria Holbox Quintana Roo",
    ],

    # ── Toluca ────────────────────────────────────────────────────────────────
    "TOLUCA": [
        "inmobiliaria Toluca Estado de México",
        "inmobiliaria Metepec Estado de México",
        "inmobiliaria Zinacantepec Toluca",
        "inmobiliaria Lerma Estado de México",
        "inmobiliaria Almoloya de Juárez",
        "inmobiliaria San Mateo Atenco",
    ],

    # ── Morelia ───────────────────────────────────────────────────────────────
    "MORELIA": [
        "inmobiliaria Morelia Michoacán",
        "inmobiliaria Morelia centro histórico",
        "inmobiliaria Morelia fraccionamiento",
        "inmobiliaria Tarímbaro Morelia",
        "inmobiliaria Lomas de Morelia",
    ],

    # ── Puebla ────────────────────────────────────────────────────────────────
    "PUEBLA": [
        "inmobiliaria Puebla centro",
        "inmobiliaria Puebla Angelópolis",
        "inmobiliaria San Andrés Cholula",
        "inmobiliaria San Pedro Cholula",
        "inmobiliaria Atlixco Puebla",
        "inmobiliaria Cuautlancingo Puebla",
    ],

    # ── Mérida ────────────────────────────────────────────────────────────────
    "MERIDA": [
        "inmobiliaria Mérida Yucatán",
        "inmobiliaria Mérida norte",
        "inmobiliaria Mérida Altabrisa",
        "inmobiliaria Mérida Temozón Norte",
        "inmobiliaria Mérida Cholul",
        "inmobiliaria Progreso Yucatán",
    ],
}


def get_queries(city: str) -> list[str]:
    key = city.upper().replace(" ", "_")
    if key not in CITIES:
        available = ", ".join(CITIES.keys())
        raise ValueError(f"Ciudad '{city}' no encontrada. Disponibles: {available}")
    return CITIES[key]


def list_cities() -> None:
    print("\nCiudades disponibles:\n")
    for city, queries in CITIES.items():
        print(f"  {city:<15} — {len(queries)} queries")
    print()
