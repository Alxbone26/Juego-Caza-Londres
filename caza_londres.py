# -*- coding: utf-8 -*-
"""
CAZA SOBRE LONDRES - Juego básico de combate aéreo (Segunda Guerra Mundial)
===========================================================================
Vista desde la cabina de un caza, de noche, sobre una Londres en llamas.

Requisitos : Python 3.10+ y Pygame 2  ->  pip install pygame-ce   (o pygame)
Ejecución  : python caza_londres.py

Controles
  A / D          : mover el avión a la izquierda / derecha
  S              : propulsión (3 s a 550 km/h, luego 15 s de espera)
  Mouse          : apuntar la mira
  Clic izquierdo : disparar (se puede mantener presionado)

Organización del código
  1. Configuración y constantes
  2. Utilidades (texto, interpolación, botones)
  3. Gráficos generados por código (sprite del enemigo)
  4. Fondo nocturno (cielo, nubes, ciudad, incendios, luces del suelo)
  5. Entidades (enemigo, avión derribado, disparos)
  6. Clase Juego (estados, lógica, cabina, instrumentos y HUD)
  7. Punto de entrada
"""
import math
import random
import sys

import pygame

# ============================================================
# 1. CONFIGURACIÓN Y CONSTANTES
# ============================================================
ANCHO, ALTO = 1280, 720
FPS = 60
CX = ANCHO // 2            # centro horizontal de la pantalla
HORIZONTE = 310            # altura del horizonte (inicio de la ciudad)
Y_ENEMIGO_MAX = 330        # los enemigos vuelan por encima de esta altura
Y_MIRA_MAX = 470           # límite inferior de la mira

# Partida
DURACION_PARTIDA = 120     # segundos
VEL_LATERAL = 320          # píxeles/segundo al presionar A o D

# Velocidad y propulsión
VEL_NORMAL = 475           # km/h
VEL_MAX = 550              # km/h
ACEL_VEL = 90              # km/h por segundo al acelerar/desacelerar
PROP_DURACION = 3.0        # segundos de propulsión activa
PROP_ESPERA = 15.0         # segundos de bloqueo posterior

# Combate
RAFAGA_DURACION = 3.0      # segundos de ataque enemigo por ráfaga
RAFAGA_INTERVALO = 6.0     # segundos entre ráfagas
DANO_POR_SEG = 5.0         # % de salud perdido por segundo de ataque
CURA_CANTIDAD = 10.0       # % de salud recuperado...
CURA_CADA = 4.0            # ...cada 4 segundos
TIEMPO_CAIDA = 3.0         # segundos seguidos de impacto para derribar
TOLERANCIA_IMPACTO = 0.30  # pausa máxima que no rompe la racha de impactos
PUNTOS_POR_ENEMIGO = 100
CADENCIA_JUGADOR = 0.07    # segundos entre salvas del jugador

# Ametralladoras (munición): se recarga sola al agotarse
MUNICION_MAX = 1200
MUN_POR_SALVA = 2          # una bala por cada ametralladora
RECARGA_TIEMPO = 2.5       # segundos de recarga automática

# Bocas de las ametralladoras (se asoman por los lados de la mira)
BOCAS = ((CX - 175, 378), (CX + 175, 378))

COLORES_LUCES = ((255, 200, 110), (255, 150, 70), (220, 220, 255), (255, 240, 180))
AMARILLO_MIRA = (236, 206, 60)

# La cabina se diseñó sobre una imagen de 1536x1024; R() convierte esas
# coordenadas de referencia a las de la ventana del juego.
REF_W, REF_H = 1536, 1024


# ============================================================
# 2. UTILIDADES
# ============================================================
def R(x, y):
    """Convierte coordenadas de la imagen de referencia a coordenadas de pantalla."""
    return (int(x * ANCHO / REF_W), int(y * ALTO / REF_H))


def limitar(v, minimo, maximo):
    """Restringe v al rango [minimo, maximo]."""
    return max(minimo, min(maximo, v))


def lerp(a, b, t):
    """Interpolación lineal entre a y b."""
    return a + (b - a) * t


def escribir(pantalla, fuente, msg, color, pos, ancla="izq", sombra=True):
    """Dibuja texto con sombra. ancla: 'izq' (esquina sup. izq.), 'centro' o 'der'."""
    img = fuente.render(msg, True, color)
    r = img.get_rect()
    if ancla == "centro":
        r.center = pos
    elif ancla == "der":
        r.midright = pos
    else:
        r.topleft = pos
    if sombra:
        pantalla.blit(fuente.render(msg, True, (0, 0, 0)), r.move(2, 2))
    pantalla.blit(img, r)


def formato_tiempo(segundos):
    """Convierte segundos a mm:ss (redondeando hacia arriba)."""
    total = max(0, math.ceil(segundos))
    return f"{total // 60:02d}:{total % 60:02d}"


class Boton:
    """Botón rectangular simple con efecto al pasar el mouse."""

    def __init__(self, rect, etiqueta, color):
        self.rect = pygame.Rect(rect)
        self.etiqueta = etiqueta
        self.color = color

    def dibujar(self, pantalla, fuente, mouse):
        activo = self.rect.collidepoint(mouse)
        fondo = tuple(min(255, c + 45) for c in self.color) if activo else self.color
        pygame.draw.rect(pantalla, fondo, self.rect, border_radius=8)
        pygame.draw.rect(pantalla, (235, 235, 235), self.rect, 2, border_radius=8)
        escribir(pantalla, fuente, self.etiqueta, (255, 255, 255), self.rect.center, "centro")

    def clic(self, pos):
        return self.rect.collidepoint(pos)


# ============================================================
# 3. GRÁFICOS GENERADOS POR CÓDIGO
# ============================================================
def crear_sprite_enemigo():
    """Caza enemigo visto desde atrás (alas anchas, deriva vertical, cabina)."""
    s = pygame.Surface((140, 64), pygame.SRCALPHA)
    verde, oscuro, claro = (62, 74, 58), (38, 46, 38), (96, 110, 92)
    pygame.draw.polygon(s, verde, [(2, 34), (48, 26), (92, 26), (138, 34), (136, 40), (92, 38), (48, 38), (4, 40)])
    pygame.draw.polygon(s, claro, [(2, 34), (14, 31), (16, 39), (4, 40)])
    pygame.draw.polygon(s, claro, [(138, 34), (126, 31), (124, 39), (136, 40)])
    pygame.draw.rect(s, (185, 185, 178), (24, 33, 12, 3))
    pygame.draw.rect(s, (185, 185, 178), (104, 33, 12, 3))
    pygame.draw.polygon(s, oscuro, [(50, 22), (90, 22), (88, 28), (52, 28)])
    pygame.draw.polygon(s, oscuro, [(64, 36), (66, 6), (76, 6), (78, 36)])
    pygame.draw.ellipse(s, (76, 88, 72), (58, 16, 24, 38))
    pygame.draw.ellipse(s, (110, 135, 145), (63, 14, 14, 15))
    pygame.draw.circle(s, (255, 150, 60), (60, 46), 2)
    pygame.draw.circle(s, (255, 150, 60), (80, 46), 2)
    return s


# ============================================================
# 4. FONDO NOCTURNO
# ============================================================
class Fondo:
    """Cielo nocturno con nubes, luna, silueta de Londres con incendios y
    luces del suelo que se desplazan según el movimiento y la velocidad."""

    ANCHO_CIUDAD = 2560
    ALTO_CIUDAD = 200

    def __init__(self):
        self.cielo = self._crear_cielo()
        self.ciudad = self._crear_ciudad()
        self.nubes = self._crear_nubes()
        self.resplandor = self._crear_resplandor(90)
        self.estrellas = [
            (random.uniform(0, ANCHO), random.uniform(0, HORIZONTE - 60),
             random.randint(90, 255), random.choice((1, 1, 2)))
            for _ in range(130)
        ]
        # Luces del suelo: [x_mundo, profundidad z, color]
        self.luces = [[random.uniform(-8, 8), random.uniform(1, 14), random.choice(COLORES_LUCES)]
                      for _ in range(260)]
        # Incendios sobre los edificios: (x en la capa de la ciudad, y en pantalla, fase)
        self.incendios = [(random.uniform(0, self.ANCHO_CIUDAD), HORIZONTE - random.uniform(8, 48),
                           random.uniform(0, 6.28)) for _ in range(11)]
        # Incendios en el suelo: [x_mundo, z]
        self.fuegos = [[random.uniform(-8, 8), random.uniform(1.5, 14)] for _ in range(10)]

    def _crear_cielo(self):
        """Degradado: azul muy oscuro arriba, resplandor anaranjado en el horizonte."""
        s = pygame.Surface((ANCHO, ALTO))
        for y in range(HORIZONTE + 1):
            t = (y / HORIZONTE) ** 2.5
            color = (int(lerp(6, 125, t)), int(lerp(9, 52, t)), int(lerp(28, 58, t)))
            pygame.draw.line(s, color, (0, y), (ANCHO, y))
        s.fill((12, 9, 13), (0, HORIZONTE, ANCHO, ALTO - HORIZONTE))   # suelo oscuro
        return s

    def _crear_resplandor(self, r):
        """Mancha de luz anaranjada (se dibuja con mezcla aditiva)."""
        s = pygame.Surface((2 * r, 2 * r))
        for i in range(r, 0, -3):
            k = (1 - i / r) ** 2
            pygame.draw.circle(s, (int(200 * k), int(90 * k), int(25 * k)), (r, r), i)
        return s

    def _crear_nubes(self):
        """Capa de nubes oscuras que se desplaza lentamente."""
        s = pygame.Surface((self.ANCHO_CIUDAD, 260), pygame.SRCALPHA)
        for _ in range(22):
            cx, cy = random.uniform(0, self.ANCHO_CIUDAD), random.uniform(40, 200)
            for _ in range(10):
                pos = (int(cx + random.gauss(0, 50)), int(cy + random.gauss(0, 12)))
                pygame.draw.circle(s, (26, 30, 52, 110), pos, random.randint(22, 52))
        return s

    def _crear_ciudad(self):
        """Silueta de edificios con ventanas encendidas y algunos monumentos."""
        w, h = self.ANCHO_CIUDAD, self.ALTO_CIUDAD
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        x = 0
        while x < w:
            ancho = random.randint(24, 70)
            alto = random.randint(25, 95)
            color = (random.randint(12, 20), random.randint(12, 20), random.randint(22, 32))
            pygame.draw.rect(s, color, (x, h - alto, ancho, alto))
            for wy in range(h - alto + 6, h - 4, 10):
                for wx in range(x + 5, x + ancho - 5, 9):
                    if random.random() < 0.12:
                        pygame.draw.rect(s, (255, 205, 110), (wx, wy, 3, 4))
            x += ancho

        sil = (9, 9, 16)
        # Big Ben
        bx = 700
        pygame.draw.rect(s, sil, (bx, h - 150, 32, 150))
        pygame.draw.rect(s, sil, (bx - 3, h - 158, 38, 10))
        pygame.draw.polygon(s, sil, [(bx - 2, h - 158), (bx + 34, h - 158), (bx + 16, h - 192)])
        pygame.draw.circle(s, (255, 235, 160), (bx + 16, h - 128), 9)
        pygame.draw.circle(s, (60, 50, 30), (bx + 16, h - 128), 9, 1)
        # London Eye
        ex, ey, r = 1250, h - 78, 70
        pygame.draw.circle(s, (150, 150, 175), (ex, ey), r, 2)
        for ang in range(0, 360, 30):
            a = math.radians(ang)
            pygame.draw.line(s, (110, 110, 135), (ex, ey), (ex + r * math.cos(a), ey + r * math.sin(a)), 1)
        for ang in range(0, 360, 24):
            a = math.radians(ang)
            pygame.draw.circle(s, (255, 220, 140), (int(ex + r * math.cos(a)), int(ey + r * math.sin(a))), 3)
        pygame.draw.line(s, sil, (ex, ey), (ex - 30, h), 3)
        pygame.draw.line(s, sil, (ex, ey), (ex + 30, h), 3)
        # Catedral de St Paul (cúpula)
        dx = 1900
        pygame.draw.rect(s, sil, (dx - 50, h - 60, 100, 60))
        pygame.draw.rect(s, sil, (dx - 28, h - 86, 56, 28))
        pygame.draw.ellipse(s, sil, (dx - 30, h - 130, 60, 90))
        pygame.draw.rect(s, sil, (dx - 4, h - 156, 8, 28))
        pygame.draw.line(s, sil, (dx, h - 170), (dx, h - 154), 2)
        pygame.draw.line(s, sil, (dx - 5, h - 164), (dx + 5, h - 164), 2)
        return s

    def actualizar(self, dt, velocidad, cam_x):
        """Las luces y fuegos del suelo se acercan al avión según la velocidad."""
        avance = (velocidad / VEL_NORMAL) * 2.2 * dt
        for luz in self.luces:
            luz[1] -= avance
            if luz[1] < 1:
                luz[1] += 13
                luz[0] = cam_x / 420.0 + random.uniform(-8, 8)
        for fuego in self.fuegos:
            fuego[1] -= avance
            if fuego[1] < 1.2:
                fuego[1] += 13
                fuego[0] = cam_x / 420.0 + random.uniform(-8, 8)

    def dibujar(self, pantalla, cam_x, t):
        pantalla.blit(self.cielo, (0, 0))
        # Estrellas (con ligero parpadeo y desplazamiento)
        for x, y, brillo, tam in self.estrellas:
            sx = (x - cam_x * 0.05 - t * 2) % ANCHO
            b = int(brillo * (0.75 + 0.25 * math.sin(t * 2 + x)))
            pygame.draw.rect(pantalla, (b, b, min(255, b + 20)), (int(sx), int(y), tam, tam))
        # Luna
        lx = int((950 - cam_x * 0.03) % (ANCHO + 120) - 60)
        pygame.draw.circle(pantalla, (18, 22, 48), (lx, 110), 62)
        pygame.draw.circle(pantalla, (30, 36, 72), (lx, 110), 44)
        pygame.draw.circle(pantalla, (228, 228, 208), (lx, 110), 26)
        # Nubes
        w = self.ANCHO_CIUDAD
        off_n = int(cam_x * 0.12 + t * 4) % w
        pantalla.blit(self.nubes, (-off_n, 10))
        pantalla.blit(self.nubes, (w - off_n, 10))
        # Ciudad (se desplaza con el movimiento lateral y una deriva constante)
        off = int(cam_x * 0.4 + t * 6) % w
        y = HORIZONTE - self.ALTO_CIUDAD
        pantalla.blit(self.ciudad, (-off, y))
        pantalla.blit(self.ciudad, (w - off, y))

        # Incendios sobre la ciudad: humo, resplandor y llamas
        for fx, fy, fase in self.incendios:
            sx = (fx - off) % w
            if sx > w - 150:
                sx -= w
            if sx > ANCHO + 150:
                continue
            for i in range(5):
                ph = (t * 0.35 + i / 5 + fase) % 1.0
                hx = sx + math.sin(fase + ph * 4) * 10 + ph * 30
                col = tuple(int(lerp(a, b, ph)) for a, b in zip((86, 52, 36), (24, 24, 32)))
                pygame.draw.circle(pantalla, col, (int(hx), int(fy - ph * 150)), int(7 + ph * 28))
            pantalla.blit(self.resplandor, (int(sx) - 90, int(fy) - 90), special_flags=pygame.BLEND_RGB_ADD)
            for _ in range(3):
                pos = (int(sx + random.uniform(-6, 6)), int(fy + random.uniform(-6, 3)))
                pygame.draw.circle(pantalla, (255, random.randint(90, 170), 25), pos, random.randint(3, 7))

        # Luces del suelo con perspectiva
        for wx, z, color in self.luces:
            rel = ((wx - cam_x / 420.0 + 8) % 16) - 8
            sx = CX + rel * 420 / z
            sy = HORIZONTE + 200 / z
            if 0 <= sx < ANCHO and sy < ALTO:
                brillo = limitar(1.25 - z / 14, 0.15, 1.0)
                c = tuple(int(v * brillo) for v in color)
                radio = int(3 / z)
                if radio <= 1:
                    pygame.draw.rect(pantalla, c, (int(sx), int(sy), 2, 2))
                else:
                    pygame.draw.circle(pantalla, c, (int(sx), int(sy)), radio)
        # Incendios del suelo
        for wx, z in self.fuegos:
            rel = ((wx - cam_x / 420.0 + 8) % 16) - 8
            sx = CX + rel * 420 / z
            sy = HORIZONTE + 200 / z
            if 0 <= sx < ANCHO and sy < ALTO:
                rr = max(2, int(18 / z))
                pos = (int(sx), int(sy))
                pygame.draw.circle(pantalla, (160, 50, 15), pos, rr + 2)
                pygame.draw.circle(pantalla, (255, random.randint(110, 170), 30), pos, rr)
                pygame.draw.circle(pantalla, (255, 230, 150), pos, max(1, rr // 2))


# ============================================================
# 5. ENTIDADES
# ============================================================
class Enemigo:
    """Avión enemigo: entra por arriba o por los lados y vuela entre puntos al azar."""

    def __init__(self, sprite_base):
        self.escala = random.uniform(0.9, 1.2)
        tam = (int(140 * self.escala), int(64 * self.escala))
        self.img = pygame.transform.smoothscale(sprite_base, tam)
        lado = random.choice(("arriba", "izq", "der"))
        if lado == "arriba":
            self.x, self.y = random.uniform(200, ANCHO - 200), -70.0
        elif lado == "izq":
            self.x, self.y = -90.0, random.uniform(60, 220)
        else:
            self.x, self.y = ANCHO + 90.0, random.uniform(60, 220)
        self.vel = random.uniform(130, 190)
        self.vx = self.vy = 0.0
        self.objetivo = self._nuevo_objetivo()
        self.entrado = False          # True cuando ya está visible en pantalla
        self.angulo = 0.0
        self.golpeado = False         # recibe disparos en este fotograma
        self.tiempo_impacto = 0.0     # segundos seguidos de impacto acumulados
        self.sin_impacto = 0.0

    @staticmethod
    def _nuevo_objetivo():
        return (random.uniform(120, ANCHO - 120), random.uniform(80, 300))

    def contiene(self, p):
        """¿El punto p (la mira) está sobre el avión? (zona elíptica)"""
        a, b = 70 * self.escala, 34 * self.escala
        return ((p[0] - self.x) / a) ** 2 + ((p[1] - self.y) / b) ** 2 <= 1

    def actualizar(self, dt, dx_jugador):
        # Al moverse el jugador, el enemigo se desplaza (efecto de paralaje)
        self.x -= dx_jugador * 0.5
        dxo, dyo = self.objetivo[0] - self.x, self.objetivo[1] - self.y
        dist = math.hypot(dxo, dyo)
        if dist < 25:
            self.objetivo = self._nuevo_objetivo()
        else:
            k = min(1.0, 2.5 * dt)
            self.vx += (dxo / dist * self.vel - self.vx) * k
            self.vy += (dyo / dist * self.vel - self.vy) * k
        self.x += self.vx * dt
        self.y += self.vy * dt

        if not self.entrado:
            if 60 <= self.x <= ANCHO - 60 and self.y >= 40:
                self.entrado = True
        else:
            self.x = limitar(self.x, 60, ANCHO - 60)
            self.y = limitar(self.y, 50, Y_ENEMIGO_MAX)
        self.angulo = limitar(-self.vx * 0.1, -28, 28)   # inclinación al girar

        # Racha de impactos: se pierde si deja de recibir disparos
        if self.golpeado:
            self.tiempo_impacto += dt
            self.sin_impacto = 0.0
        else:
            self.sin_impacto += dt
            if self.sin_impacto > TOLERANCIA_IMPACTO:
                self.tiempo_impacto = 0.0

    def dibujar(self, pantalla, atacando, t):
        img = pygame.transform.rotate(self.img, self.angulo)
        pantalla.blit(img, img.get_rect(center=(int(self.x), int(self.y))))
        # Fogonazos de las armas durante la ráfaga
        if atacando and self.entrado and int(t * 30) % 2 == 0:
            for lado in (-1, 1):
                pos = (int(self.x + lado * 34 * self.escala), int(self.y + 4))
                pygame.draw.circle(pantalla, (255, 210, 90), pos, 6)
                pygame.draw.circle(pantalla, (255, 255, 230), pos, 3)
        if not self.entrado:
            return
        # Marcador rojo de objetivo sobre el enemigo
        ty = int(self.y - 38 * self.escala - 32)
        x = int(self.x)
        pygame.draw.polygon(pantalla, (230, 40, 40), [(x - 8, ty), (x + 8, ty), (x, ty + 12)])
        # Barra de daño
        if self.tiempo_impacto > 0:
            frac = 1 - self.tiempo_impacto / TIEMPO_CAIDA
            bx, by = int(self.x - 32), int(self.y - 38 * self.escala - 10)
            pygame.draw.rect(pantalla, (60, 0, 0), (bx, by, 64, 7))
            pygame.draw.rect(pantalla, (255, 70, 50), (bx, by, int(64 * max(0, frac)), 7))
            pygame.draw.rect(pantalla, (230, 230, 230), (bx, by, 64, 7), 1)


class Caida:
    """Avión derribado: cae girando con fuego y humo (solo efecto visual)."""

    def __init__(self, enemigo):
        self.x, self.y = enemigo.x, enemigo.y
        self.vx, self.vy = random.uniform(-80, 80), -40.0
        self.rot = enemigo.angulo
        self.giro = random.choice((-1, 1)) * random.uniform(120, 260)
        self.img = enemigo.img
        self.vida = 1.6
        self.humo = []   # [x, y, radio, vida]

    def actualizar(self, dt):
        self.vida -= dt
        self.vy += 500 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rot += self.giro * dt
        self.humo.append([self.x, self.y, random.uniform(8, 14), 0.8])
        for p in self.humo:
            p[2] += 22 * dt
            p[3] -= dt
        self.humo = [p for p in self.humo if p[3] > 0]

    def dibujar(self, pantalla):
        for x, y, r, v in self.humo:
            g = int(25 + 70 * v)
            pygame.draw.circle(pantalla, (g, g, g), (int(x), int(y)), int(r))
        img = pygame.transform.rotate(self.img, self.rot)
        pantalla.blit(img, img.get_rect(center=(int(self.x), int(self.y))))
        pygame.draw.circle(pantalla, (255, random.randint(100, 170), 30),
                           (int(self.x), int(self.y)), random.randint(6, 12))


class DisparoJugador:
    """Trazador que viaja desde la boca del cañón hasta la mira."""
    DUR = 0.16

    def __init__(self, origen, destino):
        self.o, self.d, self.t = origen, destino, 0.0

    def actualizar(self, dt):
        self.t += dt / self.DUR

    @property
    def vivo(self):
        return self.t < 1.0

    def _punto(self, k):
        return (lerp(self.o[0], self.d[0], k), lerp(self.o[1], self.d[1], k))

    def dibujar(self, pantalla):
        p1 = self._punto(max(0.0, self.t - 0.35))
        p2 = self._punto(min(1.0, self.t))
        pygame.draw.line(pantalla, (255, 235, 120), p1, p2, 2)


class DisparoEnemigo:
    """Trazador enemigo que se acerca (y crece) hacia el jugador."""
    DUR = 0.45

    def __init__(self, x, y):
        self.o = (x, y)
        self.d = (CX + random.uniform(-220, 220), 500 + random.uniform(0, 40))
        self.t = 0.0

    def actualizar(self, dt):
        self.t += dt / self.DUR

    @property
    def vivo(self):
        return self.t < 1.0

    def dibujar(self, pantalla):
        def punto(k):
            return (lerp(self.o[0], self.d[0], k), lerp(self.o[1], self.d[1], k))
        pygame.draw.line(pantalla, (255, 90, 60), punto(max(0.0, self.t - 0.2)),
                         punto(min(1.0, self.t)), 1 + int(3 * self.t))


# ============================================================
# 6. JUEGO
# ============================================================
class Juego:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Caza sobre Londres")
        self.pantalla = pygame.display.set_mode((ANCHO, ALTO))
        self.reloj = pygame.time.Clock()

        nombres = "arial,segoeui,dejavusans"
        self.f_tiny = pygame.font.SysFont(nombres, 11, bold=True)
        self.f_peq = pygame.font.SysFont(nombres, 15, bold=True)
        self.f_med = pygame.font.SysFont(nombres, 22, bold=True)
        self.f_gra = pygame.font.SysFont(nombres, 34, bold=True)
        self.f_tit = pygame.font.SysFont(nombres, 54, bold=True)

        self.fondo = Fondo()
        self.sprite_enemigo = crear_sprite_enemigo()
        self.cabina = self._crear_cabina()
        self.vineta = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        self.vineta.fill((255, 0, 0, 40))
        self.velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        self.velo.fill((0, 0, 0, 170))

        # Cuadro de indicaciones iniciales (semitransparente)
        self.caja = pygame.Rect(CX - 380, 130, 760, 440)
        self.caja_fondo = pygame.Surface(self.caja.size, pygame.SRCALPHA)
        self.caja_fondo.fill((0, 0, 0, 165))
        self.b_comenzar = Boton((CX - 110, 505, 220, 46), "COMENZAR", (30, 110, 50))
        self.b_cerrar = Boton((self.caja.right - 50, self.caja.top + 14, 36, 36), "X", (120, 40, 40))

        # Botones de fin de partida
        self.b_repetir = Boton((CX - 250, 450, 230, 56), "JUGAR DE NUEVO", (30, 110, 50))
        self.b_salir = Boton((CX + 20, 450, 230, 56), "SALIR", (130, 40, 40))

        self.t = 0.0
        self.mira = (CX, 250)
        self.reiniciar()
        self.estado = "intro"      # intro -> jugando -> fin

    # ---------- Estado de la partida ----------
    def reiniciar(self):
        """Pone todas las variables de la partida en su valor inicial."""
        self.cam_x = 0.0
        self.alabeo = 0.0                   # inclinación del horizonte artificial
        self.velocidad = float(VEL_NORMAL)
        self.salud = 100.0
        self.cura_timer = 0.0
        self.puntos = 0
        self.derribados = 0
        self.tiempo_restante = float(DURACION_PARTIDA)
        self.prop_estado = "disponible"     # disponible | activa | espera
        self.prop_timer = 0.0
        self.rafaga_estado = "espera"       # espera | ataque
        self.rafaga_timer = RAFAGA_INTERVALO
        self.enemigos = [Enemigo(self.sprite_enemigo), Enemigo(self.sprite_enemigo)]
        self.caidas, self.disparos_j, self.disparos_e, self.chispas = [], [], [], []
        self.cad_jugador = 0.0
        self.cad_enemigos = 0.0
        self.destello = 0.0
        self.disparando = False
        self.apuntando = False
        self.esperar_soltar = False
        self.municion = MUNICION_MAX
        self.recargando = False
        self.recarga_timer = 0.0
        self.motivo_fin = ""

    def iniciar_partida(self):
        self.reiniciar()
        self.estado = "jugando"
        self.esperar_soltar = True          # evita disparar con el clic del botón
        pygame.mouse.set_visible(False)

    def terminar(self, motivo):
        self.estado = "fin"
        self.motivo_fin = motivo
        pygame.mouse.set_visible(True)

    @staticmethod
    def salir():
        pygame.quit()
        sys.exit()

    # ---------- Eventos ----------
    def manejar_eventos(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.salir()
            if self.estado == "intro":
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and \
                        (self.b_comenzar.clic(ev.pos) or self.b_cerrar.clic(ev.pos)):
                    self.iniciar_partida()
                elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self.iniciar_partida()
            elif self.estado == "jugando":
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_s and self.prop_estado == "disponible":
                    self.prop_estado = "activa"
                    self.prop_timer = PROP_DURACION
            elif self.estado == "fin":
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if self.b_repetir.clic(ev.pos):
                        self.iniciar_partida()
                    elif self.b_salir.clic(ev.pos):
                        self.salir()

    # ---------- Lógica ----------
    def actualizar_partida(self, dt):
        teclas = pygame.key.get_pressed()
        mov = int(teclas[pygame.K_d]) - int(teclas[pygame.K_a])
        dx = mov * VEL_LATERAL * dt
        self.cam_x += dx
        self.alabeo += (mov * 20 - self.alabeo) * min(1.0, 5 * dt)

        # Tiempo de partida
        self.tiempo_restante -= dt

        # Propulsión: disponible -> activa (3 s) -> espera (15 s) -> disponible
        if self.prop_estado in ("activa", "espera"):
            self.prop_timer -= dt
            if self.prop_timer <= 0:
                if self.prop_estado == "activa":
                    self.prop_estado, self.prop_timer = "espera", PROP_ESPERA
                else:
                    self.prop_estado, self.prop_timer = "disponible", 0.0
        objetivo = VEL_MAX if self.prop_estado == "activa" else VEL_NORMAL
        paso = ACEL_VEL * dt
        self.velocidad += limitar(objetivo - self.velocidad, -paso, paso)

        # Ráfagas enemigas: 3 s de ataque, 6 s de pausa
        self.rafaga_timer -= dt
        if self.rafaga_timer <= 0:
            if self.rafaga_estado == "espera":
                self.rafaga_estado, self.rafaga_timer = "ataque", RAFAGA_DURACION
            else:
                self.rafaga_estado, self.rafaga_timer = "espera", RAFAGA_INTERVALO
        atacando = self.rafaga_estado == "ataque"

        # Salud: daño durante la ráfaga y recuperación periódica
        if atacando:
            self.salud -= DANO_POR_SEG * dt
        self.cura_timer += dt
        while self.cura_timer >= CURA_CADA:
            self.cura_timer -= CURA_CADA
            self.salud = min(100.0, self.salud + CURA_CANTIDAD)

        # Mira y disparo del jugador
        mx, my = pygame.mouse.get_pos()
        self.mira = (mx, min(my, Y_MIRA_MAX))
        botones = pygame.mouse.get_pressed()
        if self.esperar_soltar and not botones[0]:
            self.esperar_soltar = False
        if self.recargando:                 # recarga automática de munición
            self.recarga_timer -= dt
            if self.recarga_timer <= 0:
                self.recargando = False
                self.municion = MUNICION_MAX
        self.disparando = bool(botones[0]) and not self.esperar_soltar and not self.recargando

        self.cad_jugador -= dt
        if self.disparando and self.cad_jugador <= 0:
            self.cad_jugador = CADENCIA_JUGADOR
            self.destello = 0.05
            for boca in BOCAS:
                self.disparos_j.append(DisparoJugador(boca, self.mira))
            self.municion -= MUN_POR_SALVA
            if self.municion <= 0:
                self.municion = 0
                self.recargando = True
                self.recarga_timer = RECARGA_TIEMPO

        # Enemigos: impactos, movimiento y derribos
        self.apuntando = False
        for e in self.enemigos:
            sobre = e.entrado and e.contiene(self.mira)
            self.apuntando = self.apuntando or sobre
            e.golpeado = sobre and self.disparando
            if e.golpeado:
                self.chispas.append([self.mira[0] + random.uniform(-8, 8), self.mira[1] + random.uniform(-8, 8),
                                     random.uniform(-120, 120), random.uniform(-160, 40), 0.3])
            e.actualizar(dt, dx)
        for i, e in enumerate(self.enemigos):
            if e.tiempo_impacto >= TIEMPO_CAIDA:
                self.caidas.append(Caida(e))
                self.puntos += PUNTOS_POR_ENEMIGO
                self.derribados += 1
                self.enemigos[i] = Enemigo(self.sprite_enemigo)   # siempre dos activos

        # Disparos enemigos (efecto visual) durante la ráfaga
        self.cad_enemigos -= dt
        if atacando and self.cad_enemigos <= 0:
            self.cad_enemigos = 0.07
            for e in self.enemigos:
                if e.entrado:
                    for lado in (-1, 1):
                        self.disparos_e.append(DisparoEnemigo(e.x + lado * 34 * e.escala, e.y + 4))

        # Actualizar efectos
        for lista in (self.disparos_j, self.disparos_e):
            for d in lista:
                d.actualizar(dt)
        self.disparos_j = [d for d in self.disparos_j if d.vivo]
        self.disparos_e = [d for d in self.disparos_e if d.vivo]
        for c in self.caidas:
            c.actualizar(dt)
        self.caidas = [c for c in self.caidas if c.vida > 0]
        for ch in self.chispas:
            ch[0] += ch[2] * dt
            ch[1] += ch[3] * dt
            ch[3] += 300 * dt
            ch[4] -= dt
        self.chispas = [ch for ch in self.chispas if ch[4] > 0]
        self.destello = max(0.0, self.destello - dt)

        self.fondo.actualizar(dt, self.velocidad, self.cam_x)

        # Fin de partida
        if self.salud <= 0:
            self.salud = 0
            self.terminar("¡Tu avión fue destruido!")
        elif self.tiempo_restante <= 0:
            self.tiempo_restante = 0
            self.terminar("¡Se acabó el tiempo!")

    # ---------- Cabina (parte fija, se dibuja una sola vez) ----------
    def _dibujar_ametralladora(self, s, trasera, boca):
        """Ametralladora con camisa de refrigeración, desde la cabina hacia la boca."""
        dx, dy = boca[0] - trasera[0], boca[1] - trasera[1]
        largo = math.hypot(dx, dy)
        nx, ny = -dy / largo, dx / largo

        def borde(k, w):
            x, y = trasera[0] + dx * k, trasera[1] + dy * k
            return (x + nx * w / 2, y + ny * w / 2), (x - nx * w / 2, y - ny * w / 2)

        w0, w1 = 74, 44
        a1, a2 = borde(0, w0)
        b1, b2 = borde(1, w1)
        cuerpo = [a1, b1, b2, a2]
        pygame.draw.polygon(s, (22, 22, 26), cuerpo)
        pygame.draw.polygon(s, (74, 76, 82), cuerpo, 2)
        for k in (0.25, 0.45, 0.65, 0.85):          # anillos de refrigeración
            p1, p2 = borde(k, lerp(w0, w1, k) + 4)
            pygame.draw.line(s, (62, 64, 70), p1, p2, 5)
        pygame.draw.line(s, (104, 108, 116), borde(0.02, w0 * 0.6)[0], borde(0.98, w1 * 0.6)[0], 2)
        centro = (int(boca[0]), int(boca[1]))
        pygame.draw.circle(s, (36, 38, 42), centro, int(w1 / 2) - 2)
        pygame.draw.circle(s, (96, 98, 104), centro, int(w1 / 2) - 2, 2)
        pygame.draw.circle(s, (6, 6, 8), centro, int(w1 / 2) - 12)

    @staticmethod
    def _remaches(s, a, b, n):
        """Hilera de remaches entre los puntos a y b."""
        for i in range(n):
            k = i / (n - 1) if n > 1 else 0.5
            x, y = int(lerp(a[0], b[0], k)), int(lerp(a[1], b[1], k))
            pygame.draw.circle(s, (14, 18, 12), (x, y), 4)
            pygame.draw.circle(s, (118, 132, 96), (x - 1, y - 1), 1)

    def _reloj(self, s, c, r, etiqueta, maximo, paso, subpaso, aguja=None, numeros=True):
        """Instrumento redondo con marcas ámbar sobre un barrido de 270 grados."""
        pygame.draw.circle(s, (70, 70, 74), c, r + 6)
        pygame.draw.circle(s, (124, 124, 128), c, r + 6, 2)
        pygame.draw.circle(s, (8, 8, 10), c, r)
        n = int(round(maximo / subpaso))
        for i in range(n + 1):
            a = math.radians(135 + 270 * i / n)
            cs, sn = math.cos(a), math.sin(a)
            valor = i * subpaso
            grande = abs((valor / paso) - round(valor / paso)) < 1e-6
            r2 = r - (14 if grande else 9)
            pygame.draw.line(s, (235, 165, 70), (c[0] + (r - 4) * cs, c[1] + (r - 4) * sn),
                             (c[0] + r2 * cs, c[1] + r2 * sn), 2 if grande else 1)
            if grande and numeros:
                img = self.f_tiny.render(str(int(valor)), True, (235, 165, 70))
                s.blit(img, img.get_rect(center=(c[0] + (r - 25) * cs, c[1] + (r - 25) * sn)))
        if etiqueta:
            img = self.f_tiny.render(etiqueta, True, (235, 165, 70))
            s.blit(img, img.get_rect(center=(c[0], c[1] + r * 0.5)))
        if aguja is not None:
            a = math.radians(135 + 270 * aguja)
            pygame.draw.line(s, (235, 235, 235), c, (c[0] + (r - 10) * math.cos(a), c[1] + (r - 10) * math.sin(a)), 2)
            pygame.draw.circle(s, (180, 180, 180), c, 4)

    def _crear_cabina(self):
        """Dibuja las partes fijas de la cabina: ametralladoras, marco verde oliva
        con remaches, panel negro con relojes y soporte de la mira."""
        s = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        oliva, oliva_osc, oliva_luz = (44, 54, 36), (20, 26, 16), (100, 114, 76)

        def poli(puntos_ref, color=oliva, borde=oliva_osc):
            pts = [R(*p) for p in puntos_ref]
            pygame.draw.polygon(s, color, pts)
            pygame.draw.polygon(s, borde, pts, 3)
            return pts

        # 1. Ametralladoras (detrás del marco y del tablero)
        for lado in (-1, 1):
            self._dibujar_ametralladora(s, (CX + lado * 325, 492), (CX + lado * 175, 378))

        # 2. Marco del parabrisas: rieles, travesaño superior y montantes
        poli([(0, 0), (300, 0), (292, 38), (205, 125), (40, 170), (0, 330)])             # riel izquierdo
        poli([(1250, 0), (1536, 0), (1536, 330), (1496, 170), (1396, 125), (1340, 45)])  # riel derecho
        poli([(440, 0), (1062, 0), (1040, 16), (462, 16)])                               # travesaño
        poli([(205, 125), (292, 38), (395, 690), (300, 705)])                            # montante izq.
        poli([(1045, 0), (1122, 0), (1205, 700), (1112, 705)])                           # montante der.
        pygame.draw.line(s, oliva_luz, R(292, 38), R(395, 690), 2)
        pygame.draw.line(s, oliva_luz, R(1045, 0), R(1112, 705), 2)
        self._remaches(s, R(250, 85), R(348, 695), 9)
        self._remaches(s, R(1083, 10), R(1158, 700), 9)
        self._remaches(s, R(60, 40), R(235, 100), 5)
        self._remaches(s, R(1300, 25), R(1500, 220), 6)
        self._remaches(s, R(520, 8), R(990, 8), 8)

        # 3. Borde superior del tablero (verde oliva) y panel de instrumentos (negro)
        coaming = [(0, 1024), (0, 870), (120, 800), (300, 720), (420, 680), (560, 650), (640, 640),
                   (900, 640), (990, 650), (1130, 690), (1300, 740), (1450, 800), (1536, 870), (1536, 1024)]
        poli(coaming, (38, 48, 32), oliva_osc)
        pygame.draw.lines(s, oliva_luz, False, [R(*p) for p in coaming[1:-1]], 3)
        self._remaches(s, R(60, 880), R(380, 720), 5)
        self._remaches(s, R(1156, 700), R(1480, 860), 5)
        panel = [(0, 1024), (0, 925), (130, 860), (330, 790), (520, 750), (640, 742),
                 (900, 742), (1010, 750), (1200, 790), (1400, 860), (1536, 925), (1536, 1024)]
        poli(panel, (12, 12, 14), (52, 54, 58))

        # 4. Relojes: velocidad, altímetro, indicador de actitud y otros
        self.c_vel, self.r_vel = (440, 592), 62
        self.c_act, self.r_act = (633, 606), 56
        self._reloj(s, self.c_vel, self.r_vel, "AIRSPEED km/h", 600, 100, 50)
        self._reloj(s, (812, 592), 62, "ALTITUDE m", 10, 1, 0.5, aguja=0.32)
        self._reloj(s, (345, 625), 36, "", 8, 2, 1, aguja=0.5, numeros=False)
        self._reloj(s, (392, 690), 28, "", 8, 2, 1, aguja=0.7, numeros=False)
        self._reloj(s, (850, 696), 30, "N", 8, 2, 1, aguja=0.1, numeros=False)
        self._reloj(s, (1215, 650), 34, "", 8, 2, 1, aguja=0.8, numeros=False)
        pygame.draw.circle(s, (70, 70, 74), self.c_act, self.r_act + 6)
        pygame.draw.circle(s, (124, 124, 128), self.c_act, self.r_act + 6, 2)

        # 5. Soporte de la mira reflectora (en forma de U) al centro
        negro, gris = (10, 10, 12), (70, 72, 78)
        for rect in ((640, 535, 40, 205), (855, 535, 40, 205), (640, 640, 255, 100)):
            x, y = R(rect[0], rect[1])
            x2, y2 = R(rect[0] + rect[2], rect[1] + rect[3])
            pygame.draw.rect(s, negro, (x, y, x2 - x, y2 - y))
            pygame.draw.rect(s, gris, (x, y, x2 - x, y2 - y), 2)
        x, y = R(690, 615)
        x2, y2 = R(845, 685)
        pygame.draw.ellipse(s, (34, 38, 28), (x, y, x2 - x, y2 - y))
        pygame.draw.ellipse(s, (110, 120, 90), (x, y, x2 - x, y2 - y), 2)
        return s

    # ---------- Instrumentos y HUD (parte dinámica) ----------
    def dibujar_instrumentos(self):
        p = self.pantalla
        # Aguja del velocímetro (0-600 km/h)
        c, r = self.c_vel, self.r_vel
        a = math.radians(135 + 270 * limitar(self.velocidad / 600.0, 0, 1))
        pygame.draw.line(p, (255, 170, 60), c, (c[0] + (r - 8) * math.cos(a), c[1] + (r - 8) * math.sin(a)), 3)
        pygame.draw.circle(p, (200, 200, 200), c, 5)

        # Indicador de actitud: el horizonte se inclina al mover el avión
        c, r = self.c_act, self.r_act - 2
        b = math.radians(self.alabeo)
        pygame.draw.circle(p, (70, 45, 30), c, r)
        cielo = [(c[0] + r * math.cos(b + math.radians(d)), c[1] + r * math.sin(b + math.radians(d)))
                 for d in range(180, 361, 10)]
        pygame.draw.polygon(p, (20, 95, 125), cielo)
        pygame.draw.line(p, (235, 235, 235), (c[0] - r * math.cos(b), c[1] - r * math.sin(b)),
                         (c[0] + r * math.cos(b), c[1] + r * math.sin(b)), 2)
        pygame.draw.line(p, (255, 190, 60), (c[0] - 26, c[1]), (c[0] - 9, c[1]), 3)
        pygame.draw.line(p, (255, 190, 60), (c[0] + 9, c[1]), (c[0] + 26, c[1]), 3)
        pygame.draw.polygon(p, (255, 190, 60), [(c[0], c[1] - 6), (c[0] - 6, c[1] + 6), (c[0] + 6, c[1] + 6)])

    def _caja(self, rect, alpha=150):
        """Caja translúcida oscura para los indicadores del HUD."""
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        s.fill((0, 0, 0, alpha))
        self.pantalla.blit(s, rect.topleft)
        pygame.draw.rect(self.pantalla, (190, 190, 190), rect, 1)

    def dibujar_velocimetro(self):
        """SPD y regla vertical de velocidad (escala 400-600 km/h) al costado izquierdo."""
        p = self.pantalla
        escribir(p, self.f_peq, "SPD", (235, 235, 235), (14, 248))
        escribir(p, self.f_gra, str(int(round(self.velocidad))), (255, 255, 255), (14, 264))
        escribir(p, self.f_peq, "km/h", (235, 235, 235), (14, 304))
        x_lin, y_alto, y_bajo = 52, 340, 540          # 1 píxel = 1 km/h
        pygame.draw.line(p, (235, 235, 235), (x_lin, y_alto), (x_lin, y_bajo), 2)
        for v in range(400, 601, 10):
            y = y_bajo - (v - 400)
            largo = 14 if v % 50 == 0 else 7
            pygame.draw.line(p, (235, 235, 235), (x_lin - largo, y), (x_lin, y), 1)
            if v % 50 == 0:
                escribir(p, self.f_peq, str(v), (235, 235, 235), (x_lin - largo - 4, y), "der")
        y_v = y_bajo - limitar(self.velocidad - 400, 0, 200)
        pygame.draw.rect(p, (70, 220, 90), (x_lin + 3, int(y_v), 5, int(y_bajo - y_v)))
        pygame.draw.polygon(p, (255, 255, 255), [(x_lin + 9, int(y_v)), (x_lin + 20, int(y_v) - 6),
                                                 (x_lin + 20, int(y_v) + 6)])

    def dibujar_salud(self):
        """Indicador SALUD con icono de avión (abajo a la izquierda)."""
        p = self.pantalla
        box = pygame.Rect(20, 642, 272, 52)
        self._caja(box)
        cx, cy = box.x + 28, box.centery
        avion = [(0, -14), (3, -4), (18, 3), (18, 6), (3, 3), (3, 10), (8, 13), (8, 15), (0, 13),
                 (-8, 15), (-8, 13), (-3, 10), (-3, 3), (-18, 6), (-18, 3), (-3, -4)]
        pygame.draw.polygon(p, (240, 240, 240), [(cx + a, cy + b) for a, b in avion])
        escribir(p, self.f_peq, "SALUD", (240, 240, 240), (box.x + 60, box.y + 6))
        frac = limitar(self.salud / 100.0, 0, 1)
        color = (70, 200, 80) if frac > 0.6 else (240, 180, 40) if frac > 0.3 else (220, 50, 40)
        barra = pygame.Rect(box.x + 60, box.y + 28, 150, 14)
        pygame.draw.rect(p, (40, 40, 40), barra)
        pygame.draw.rect(p, color, (barra.x, barra.y, int(barra.w * frac), barra.h))
        escribir(p, self.f_med, f"{int(math.ceil(self.salud))}%", (255, 255, 255),
                 (box.right - 10, box.y + 34), "der")

    def dibujar_municion(self):
        """Indicador AMETRALLADORAS con balas y contador (a la derecha del tablero)."""
        p = self.pantalla
        box = pygame.Rect(900, 566, 250, 74)
        self._caja(box)
        escribir(p, self.f_peq, "AMETRALLADORAS", (240, 240, 240), (box.x + 10, box.y + 6))
        llenas = math.ceil(7 * self.municion / MUNICION_MAX)
        for i in range(7):
            x, y = box.x + 12 + i * 13, box.y + 34
            col = (240, 240, 235) if i < llenas else (70, 70, 70)
            pygame.draw.rect(p, col, (x, y + 6, 7, 18))
            pygame.draw.polygon(p, col, [(x, y + 6), (x + 7, y + 6), (x + 3, y)])
        if self.recargando:
            if int(self.t * 4) % 2 == 0:
                escribir(p, self.f_med, "RECARGANDO", (255, 170, 40), (box.x + 112, box.y + 38))
        else:
            txt = str(int(self.municion))
            escribir(p, self.f_gra, txt, (255, 255, 255), (box.x + 112, box.y + 30))
            ancho = self.f_gra.size(txt)[0]
            escribir(p, self.f_peq, f"/ {MUNICION_MAX}", (200, 200, 200), (box.x + 118 + ancho, box.y + 46))

    def dibujar_propulsion(self):
        """Estado de la propulsión: disponible, activa o en espera, con tiempo restante."""
        p = self.pantalla
        box = pygame.Rect(906, 646, 250, 56)
        self._caja(box)
        escribir(p, self.f_peq, "PROPULSIÓN  [S]", (240, 240, 240), (box.x + 10, box.y + 4))
        if self.prop_estado == "disponible":
            txt, col, frac = "DISPONIBLE", (80, 220, 100), 1.0
        elif self.prop_estado == "activa":
            txt, col = f"ACTIVA  {self.prop_timer:0.1f} s", (255, 170, 40)
            frac = self.prop_timer / PROP_DURACION
        else:
            txt, col = f"EN ESPERA  {self.prop_timer:0.1f} s", (230, 90, 70)
            frac = 1 - self.prop_timer / PROP_ESPERA
        escribir(p, self.f_med, txt, col, (box.x + 10, box.y + 19))
        pygame.draw.rect(p, (40, 40, 40), (box.x + 10, box.y + 47, 230, 5))
        pygame.draw.rect(p, col, (box.x + 10, box.y + 47, int(230 * limitar(frac, 0, 1)), 5))

    def dibujar_hud_superior(self):
        p = self.pantalla
        escribir(p, self.f_gra, f"PUNTOS: {self.puntos}", (255, 235, 120), (310, 26))
        escribir(p, self.f_gra, f"TIEMPO {formato_tiempo(self.tiempo_restante)}", (255, 255, 255), (CX, 52), "centro")
        if self.rafaga_estado == "ataque" and int(self.t * 4) % 2 == 0:
            escribir(p, self.f_gra, "¡ATAQUE ENEMIGO!", (255, 70, 60), (CX, 92), "centro")

    def dibujar_mira(self):
        """Mira amarilla: círculo con cruz, círculo interior y puntos (sigue al mouse)."""
        p = self.pantalla
        x, y = self.mira
        color = (255, 90, 60) if self.apuntando else AMARILLO_MIRA
        pygame.draw.circle(p, color, (x, y), 46, 2)
        pygame.draw.circle(p, color, (x, y), 14, 2)
        pygame.draw.circle(p, color, (x, y), 2)
        for (a, b, c, d) in ((-58, 0, -14, 0), (14, 0, 58, 0), (0, -58, 0, -14), (0, 14, 0, 58)):
            pygame.draw.line(p, color, (x + a, y + b), (x + c, y + d), 2)
        for ang in (45, 135, 225, 315):
            q = math.radians(ang)
            pygame.draw.circle(p, color, (int(x + 30 * math.cos(q)), int(y + 30 * math.sin(q))), 2)

    # ---------- Dibujo: escena completa ----------
    def dibujar(self):
        p = self.pantalla
        self.fondo.dibujar(p, self.cam_x, self.t)
        atacando = self.rafaga_estado == "ataque"

        if self.estado != "intro":
            for c in self.caidas:
                c.dibujar(p)
            for e in self.enemigos:
                e.dibujar(p, atacando, self.t)
            for d in self.disparos_e:
                d.dibujar(p)
            for d in self.disparos_j:
                d.dibujar(p)
            for x, y, _, _, vida in self.chispas:
                pygame.draw.circle(p, (255, 200, 80), (int(x), int(y)), 2 if vida < 0.15 else 3)

        p.blit(self.cabina, (0, 0))
        if self.destello > 0:                       # fogonazos en las bocas
            for boca in BOCAS:
                r = random.randint(14, 24)
                pygame.draw.circle(p, (255, 150, 40), boca, r)
                pygame.draw.circle(p, (255, 220, 120), boca, int(r * 0.6))
                pygame.draw.circle(p, (255, 255, 240), boca, int(r * 0.3))
                for _ in range(4):
                    ang = random.uniform(0, 6.28)
                    pygame.draw.line(p, (255, 210, 90), boca,
                                     (boca[0] + r * 1.8 * math.cos(ang), boca[1] + r * 1.8 * math.sin(ang)), 2)
        self.dibujar_instrumentos()

        self.dibujar_velocimetro()
        self.dibujar_salud()
        self.dibujar_municion()
        self.dibujar_propulsion()
        if self.estado != "intro":
            self.dibujar_hud_superior()
            if atacando and self.estado == "jugando":
                p.blit(self.vineta, (0, 0))
        if self.estado == "jugando":
            self.dibujar_mira()

        mouse = pygame.mouse.get_pos()
        if self.estado == "intro":
            self.dibujar_intro(mouse)
        elif self.estado == "fin":
            self.dibujar_fin(mouse)

    def dibujar_intro(self, mouse):
        p = self.pantalla
        p.blit(self.caja_fondo, self.caja.topleft)
        pygame.draw.rect(p, (200, 210, 190), self.caja, 2, border_radius=6)
        escribir(p, self.f_tit, "INDICACIONES DE VUELO", (255, 235, 120), (CX, self.caja.y + 52), "centro")
        filas = (("A", "Mover el avión a la izquierda"),
                 ("D", "Mover el avión a la derecha"),
                 ("S", "Propulsión: 550 km/h durante 3 s (recarga de 15 s)"),
                 ("MOUSE", "Apuntar la mira"),
                 ("CLIC IZQUIERDO", "Disparar hacia la mira"))
        y = self.caja.y + 105
        for tecla, desc in filas:
            escribir(p, self.f_med, tecla, (255, 200, 90), (self.caja.x + 50, y))
            escribir(p, self.f_med, desc, (255, 255, 255), (self.caja.x + 270, y))
            y += 42
        escribir(p, self.f_peq, "Derriba aviones enemigos antes de que se acaben los 2 minutos. "
                 "Mantén el disparo sobre un enemigo 3 segundos para derribarlo.",
                 (210, 220, 200), (CX, self.caja.y + 335), "centro")
        self.b_comenzar.dibujar(p, self.f_med, mouse)
        self.b_cerrar.dibujar(p, self.f_med, mouse)

    def dibujar_fin(self, mouse):
        p = self.pantalla
        p.blit(self.velo, (0, 0))
        escribir(p, self.f_tit, "FIN DE LA PARTIDA", (255, 235, 120), (CX, 190), "centro")
        escribir(p, self.f_med, self.motivo_fin, (255, 255, 255), (CX, 255), "centro")
        escribir(p, self.f_tit, f"Puntuación final: {self.puntos}", (255, 255, 255), (CX, 330), "centro")
        escribir(p, self.f_med, f"Aviones derribados: {self.derribados}", (210, 220, 200), (CX, 390), "centro")
        self.b_repetir.dibujar(p, self.f_med, mouse)
        self.b_salir.dibujar(p, self.f_med, mouse)

    # ---------- Bucle principal ----------
    def ejecutar(self):
        while True:
            dt = min(self.reloj.tick(FPS) / 1000.0, 0.05)   # 60 FPS constantes
            self.t += dt
            self.manejar_eventos()
            if self.estado == "intro":
                self.fondo.actualizar(dt, VEL_NORMAL, self.cam_x)
            elif self.estado == "jugando":
                self.actualizar_partida(dt)
            self.dibujar()
            pygame.display.flip()


# ============================================================
# 7. PUNTO DE ENTRADA
# ============================================================
if __name__ == "__main__":
    Juego().ejecutar()
