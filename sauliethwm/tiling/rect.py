"""
sauliethwm.tiling.rect - Estructura geometrica Rect.

Define un rectangulo inmutable que representa un area de pantalla.
Se usa para describir tanto el area disponible del monitor como
las coordenadas destino de cada ventana en un layout.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Rect:
    """
    Rectangulo inmutable definido por posicion (x, y) y dimensiones (w, h).

    Todas las coordenadas estan en pixeles. El origen (0, 0) es la esquina
    superior-izquierda del monitor primario.

    Atributos:
        x: Coordenada horizontal de la esquina superior-izquierda.
        y: Coordenada vertical de la esquina superior-izquierda.
        w: Ancho en pixeles.
        h: Alto en pixeles.
    """

    x: int
    y: int
    w: int
    h: int

    # ------------------------------------------------------------------
    # Propiedades derivadas
    # ------------------------------------------------------------------
    @property
    def left(self) -> int:
        return self.x

    @property
    def top(self) -> int:
        return self.y

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def center_x(self) -> int:
        return self.x + self.w // 2

    @property
    def center_y(self) -> int:
        return self.y + self.h // 2

    @property
    def area(self) -> int:
        return self.w * self.h

    # ------------------------------------------------------------------
    # Operaciones geometricas
    # ------------------------------------------------------------------
    def split_horizontal(self, ratio: float = 0.5) -> tuple[Rect, Rect]:
        """
        Divide el rectangulo verticalmente (columna izquierda / derecha).

        Args:
            ratio: Fraccion del ancho para la parte izquierda (0.0 - 1.0).

        Returns:
            Tupla (izquierda, derecha).
        """
        left_w = int(self.w * ratio)
        right_w = self.w - left_w
        left = Rect(self.x, self.y, left_w, self.h)
        right = Rect(self.x + left_w, self.y, right_w, self.h)
        return left, right

    def split_vertical(self, ratio: float = 0.5) -> tuple[Rect, Rect]:
        """
        Divide el rectangulo horizontalmente (fila superior / inferior).

        Args:
            ratio: Fraccion del alto para la parte superior (0.0 - 1.0).

        Returns:
            Tupla (superior, inferior).
        """
        top_h = int(self.h * ratio)
        bottom_h = self.h - top_h
        top = Rect(self.x, self.y, self.w, top_h)
        bottom = Rect(self.x, self.y + top_h, self.w, bottom_h)
        return top, bottom

    def slice_rows(self, count: int) -> list[Rect]:
        """
        Divide el rectangulo en *count* filas de igual alto.

        Args:
            count: Numero de filas.

        Returns:
            Lista de Rect, de arriba hacia abajo.
        """
        if count <= 0:
            return []
        if count == 1:
            return [self]

        base_h = self.h // count
        rects: list[Rect] = []
        y = self.y

        for i in range(count):
            # La ultima fila absorbe los pixeles sobrantes
            h = base_h if i < count - 1 else self.h - (y - self.y)
            rects.append(Rect(self.x, y, self.w, h))
            y += h

        return rects

    def slice_columns(self, count: int) -> list[Rect]:
        """
        Divide el rectangulo en *count* columnas de igual ancho.

        Args:
            count: Numero de columnas.

        Returns:
            Lista de Rect, de izquierda a derecha.
        """
        if count <= 0:
            return []
        if count == 1:
            return [self]

        base_w = self.w // count
        rects: list[Rect] = []
        x = self.x

        for i in range(count):
            w = base_w if i < count - 1 else self.w - (x - self.x)
            rects.append(Rect(x, self.y, w, self.h))
            x += w

        return rects

    def pad(self, gap: int) -> Rect:
        """
        Reduce el rectangulo aplicando un margen interior (gap) uniforme.

        Args:
            gap: Pixeles de margen en cada lado.

        Returns:
            Nuevo Rect reducido. Si el gap es mayor que las dimensiones,
            retorna un Rect de tamano 0 centrado.
        """
        new_w = max(0, self.w - 2 * gap)
        new_h = max(0, self.h - 2 * gap)
        return Rect(self.x + gap, self.y + gap, new_w, new_h)

    # ------------------------------------------------------------------
    # Conversion a tupla Win32 (left, top, right, bottom)
    # ------------------------------------------------------------------
    def to_ltrb(self) -> tuple[int, int, int, int]:
        """Retorna (left, top, right, bottom) para compatibilidad Win32."""
        return (self.left, self.top, self.right, self.bottom)

    @classmethod
    def from_ltrb(cls, left: int, top: int, right: int, bottom: int) -> Rect:
        """Crea un Rect desde coordenadas (left, top, right, bottom)."""
        return cls(left, top, right - left, bottom - top)

    # ------------------------------------------------------------------
    # Representacion
    # ------------------------------------------------------------------
    def __str__(self) -> str:
        return f"Rect({self.w}x{self.h}+{self.x}+{self.y})"
