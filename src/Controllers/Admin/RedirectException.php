<?php

namespace Cauri\Controllers\Admin;

/** Interrompt une action pour rediriger (page de connexion). */
final class RedirectException extends \RuntimeException
{
    public function __construct(public readonly string $to)
    {
        parent::__construct($to);
    }
}
