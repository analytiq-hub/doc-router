from bson import ObjectId
import logging
from typing import List

async def delete_user(db, user_id: str) -> bool:
    """
    Delete a single user and clean up all associated data.
    Removes user from all organizations and deletes organizations where they were the last member.
    
    Args:
        db: MongoDB database instance
        user_id: ID of the user to delete
        
    Returns:
        bool: True if user was deleted, False if user was not found
    """
    try:
        # Find all organizations where user is a member
        async for org in db.organizations.find({"members.user_id": user_id}):
            if len(org["members"]) == 1:
                # If user is the only member, delete the organization
                await db.organizations.delete_one({"_id": org["_id"]})
                logging.info(f"Deleted organization {org['_id']} as user was the last member")
            else:
                # Otherwise, remove user from organization
                await db.organizations.update_one(
                    {"_id": org["_id"]},
                    {"$pull": {"members": {"user_id": user_id}}}
                )
                logging.info(f"Removed user {user_id} from organization {org['_id']}")

        # Delete user's OAuth accounts
        await db.accounts.delete_many({"userId": user_id})
        
        # Delete the user
        result = await db.users.delete_one({"_id": ObjectId(user_id)})
        
        if result.deleted_count == 0:
            logging.warning(f"User {user_id} not found")
            return False
            
        logging.info(f"Successfully deleted user {user_id} and all associated data")
        return True
        
    except Exception as e:
        logging.error(f"Error deleting user {user_id}: {str(e)}")
        raise