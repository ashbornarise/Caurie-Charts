<?php

namespace Cauri\Services\Platforms;

final class QuotaExceededException extends PlatformException
{
    /** @param array $partial résultats déjà obtenus avant l'épuisement du quota */
    public function __construct(string $message, public readonly array $partial = [])
    {
        parent::__construct($message);
    }
}
