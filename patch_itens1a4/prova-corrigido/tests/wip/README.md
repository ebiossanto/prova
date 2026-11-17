# tests/wip: casos "proibidos" que ainda não testam o que dizem

Os quatro `.prova` daqui descrevem padrões a rejeitar (escape de atomic, aliasing mutável, shift sem
limite, assinatura imutável no laço de IA), mas hoje não contêm o padrão proibido ou usam construções
inexistentes (`shl`, `u32`). Reescreva-os com sintaxe real e mova para `tests/` junto com um teste que
exija a rejeição.
