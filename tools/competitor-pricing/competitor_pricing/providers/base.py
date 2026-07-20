from abc import ABC, abstractmethod

from ..models import PropertyReport


class AirbnbDataProvider(ABC):
    """Interface for a paid third-party Airbnb data source.

    Airbnb has no public API and blocks scraping, so this tool never talks
    to Airbnb directly. Instead it talks to whatever provider you've signed
    up with (AirDNA, Rabbu, AirROI, Mashvisor, PriceLabs, ...) through their
    own API. Implement `fetch` against that vendor's real contract.
    """

    @abstractmethod
    def fetch(self, listing_id: str) -> PropertyReport:
        raise NotImplementedError
