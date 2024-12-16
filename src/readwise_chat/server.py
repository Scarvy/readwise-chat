# /// script
# dependencies = [
#   "mcp"
# ]
# ///
import logging
import os
from datetime import datetime
from time import sleep
from typing import Optional

import httpx
import mcp.server.stdio
import mcp.types as types
from dotenv import load_dotenv
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

from .models import Document, GetResponse, PostRequest, PostResponse

# Store documents as a simple key-value dict to demonstrate state management
documents: dict[str, Document] = {}

load_dotenv()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("readwise-chat")

API_KEY = os.getenv("READWISE_API_KEY")
if not API_KEY:
    raise ValueError("Missing READWISE_API_KEY in environment")

API_BASE_URL = "https://readwise.io/api/v3"
LIST_ENDPOINT = "list"
SAVE_ENDPOINT = "save"
DEFAULT_LOCATION = "new"
DEFAULT_CATEGORY = "article"
DEFAULT_DOCUMENT_TITLE = "Getting Started with Reader"
DEFAULT_INCLUDE_HTML_CONTENT = True

VALID_LOCATIONS = ("new", "later", "shortlist", "archive", "feed")
VALID_CATEGORIES = (
    "article",
    "email",
    "rss",
    "highlight",
    "note",
    "pdf",
    "epub",
    "tweet",
    "video",
)


async def _get_request(params: dict[str, str]) -> GetResponse:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url=f"{API_BASE_URL}/{LIST_ENDPOINT}",
            headers={"Authorization": f"Token {API_KEY}"},
            params=params,
        )

        if response.status_code != 429:
            return GetResponse(**response.json())

        wait_time = int(response.headers["Retry-After"])
        sleep(wait_time)
        return await _get_request(params)


async def _post_request(payload: PostRequest) -> tuple[bool, PostResponse]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=f"{API_BASE_URL}/{SAVE_ENDPOINT}",
            headers={"Authorization": f"Token {API_KEY}"},
            json=payload.model_dump(),
        )

        if response.raise_for_status():
            return (False, PostResponse())

        if response.status_code != 429:
            return (response.status_code == 200, PostResponse(**response.json()))

        wait_time = int(response.headers["Retry-After"])
        sleep(wait_time)
        return await _post_request(payload)


def format_document(document: Document) -> str:
    return (
        f"Title: {document.title if document.title else "Unknown"}\n",
        f"Author: {document.author if document.author else "Unknown"}\n",
        f"Category: {document.category if document.category else "Unknown"}\n",
        f"Location: {document.location if document.location else "Unknown"}\n",
        f"Tags: {document.tags if document.tags else "None"}\n",
        f"Word Count: {document.word_count if document.word_count else "Unknown"}\n",
        f"Published Date: {document.published_date if document.published_date else "Unknown"}\n",
        f"Summary: {document.summary if document.summary else "None"}\n",
        f"Source URL: {document.source_url if document.source_url else "Unknown"}\n",
        f"HTML Content: {document.html_content if document.html_content else "None"}\n",
    )


def format_iso_datetime(date: str) -> str:
    return datetime.fromisoformat(date).isoformat()


async def fetch_documents(
    location: str, category: Optional[str] = None, updated_after: Optional[str] = None
) -> list[Document]:
    params = {}
    if location not in VALID_LOCATIONS:
        raise ValueError(f"Invalid location: {location}")

    params["location"] = location
    if category:
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {category}")
        params["category"] = category

    if updated_after:
        params["updatedAfter"] = updated_after

    params["withHtmlContent"] = DEFAULT_INCLUDE_HTML_CONTENT

    results: list[Document] = []
    while (response := await _get_request(params)).next_page_cursor:
        results.extend(response.results)
        params["pageCursor"] = response.next_page_cursor
    else:
        # Make sure not to forget last response where `next_page_cursor` is None.
        results.extend(response.results)

    return results


async def save_document(url: str) -> tuple[bool, PostResponse]:
    return await _post_request(PostRequest(url=url))


server = Server("readwise-chat")


@server.list_resources()
async def list_resources() -> list[types.Resource]:
    """
    List available documents resources.
    Each document is exposed as a resource with a custom document:// URI scheme.
    """
    return [
        types.Resource(
            uri=AnyUrl(f"readwise://list/{document.title}"),
            name=f"Document: {document.title}",
            description=f"{document.summary if document.summary else "No summary available"}",
            mimeType="application/json",
        )
        for document in documents
    ]


@server.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """
    Read a specific documents's content by its URI.
    The document title is extracted from the URI host component.
    """
    if uri.scheme != "document":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    name = uri.path
    if name is not None:
        name = name.lstrip("/")
        return documents[name]
    raise ValueError(f"Note not found: {name}")


# @server.list_prompts()
# async def handle_list_prompts() -> list[types.Prompt]:
#     """
#     List available prompts.
#     Each prompt can have optional arguments to customize its behavior.
#     """
#     return [
#         types.Prompt(
#             name="list-documents-by-location",
#             description="List documents by location",
#             arguments=[
#                 types.PromptArgument(
#                     name="style",
#                     description="The style of the list",
#                     required=False,
#                 )
#             ],
#         )
#     ]


@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate a prompt by combining arguments with server state.
    The prompt includes all current notes and can be customized via arguments.
    """
    if name != "summarize-notes":
        raise ValueError(f"Unknown prompt: {name}")

    style = (arguments or {}).get("style", "brief")
    detail_prompt = " Give extensive details." if style == "detailed" else ""

    return types.GetPromptResult(
        description="Summarize the current notes",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"Here are the current notes to summarize:{detail_prompt}\n\n"
                    + "\n".join(
                        f"- {name}: {content}" for name, content in documents.items()
                    ),
                ),
            )
        ],
    )


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools.
    Each tool specifies its arguments using JSON Schema validation.
    """
    return [
        types.Tool(
            name="add-document",
            description="Add a new document to Readwise Reader",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                },
                "required": ["url"],
            },
        ),
        types.Tool(
            name="get-document",
            description="Get a list of documents from Readwise Reader",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The document's location, could be one of: new, later, shortlist, archive, feed",
                    },
                    "category": {
                        "type": "string",
                        "description": "The document's category, could be one of: article, email, rss, highlight, note, pdf, epub, tweet, video",
                    },
                    "updated_after": {
                        "type": "string",
                        "description": "Fetch only documents updated after this date",
                    },
                },
                "required": ["location"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests.
    Tools can modify server state and notify clients of changes.
    """
    if not arguments:
        raise ValueError("Missing arguments")

    if name == "add-document":
        url = arguments.get("url")

        if not url:
            raise ValueError("Missing name or content")

        document_already_exists, response = await save_document(url)

        if document_already_exists:
            logger.info(f"Document already exists with the ID: {response.id}")
            text = types.TextContent(
                type="text",
                text=f"Document already exists with the ID: {response.id}",
            )
        else:
            logger.info(f"Added document: {response.id}")
            text = types.TextContent(
                type="text",
                text=f"Added document with the ID: {response.id}",
            )

        # Notify clients that resources have changed
        await server.request_context.session.send_resource_list_changed()
        return [text]

    elif name == "get-document":
        logger.info(f"Arguments: {arguments}")
        location = arguments.get("location")
        category = arguments.get("category")
        updated_after = arguments.get("updated_after")

        updated_after_formatted = (
            format_iso_datetime(updated_after) if updated_after else None
        )

        if not location:
            logger.error(f"Missing location: {location}")
            raise ValueError("Missing location or category")

        fetched_documents = await fetch_documents(
            location, category, updated_after_formatted
        )

        if not fetched_documents:
            logger.info("No documents found")
            return [
                types.TextContent(
                    type="text",
                    text="No documents found.",
                )
            ]

        # add documents to the server state
        for doc in fetched_documents:
            documents[doc.title] = doc

        # Notify clients that resources have changed
        await server.request_context.session.send_resource_list_changed()

        logger.info(f"Fetched {len(fetched_documents)} documents")
        formated_text = "\n".join(
            "\n".join(format_document(document)) for document in fetched_documents
        )

        return [
            types.TextContent(
                type="text",
                text=f"{len(fetched_documents)} documents found:\n{formated_text}",
            )
        ]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="readwise-chat",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
